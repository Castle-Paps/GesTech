from django.db import models
from django.conf import settings
from catalogo.models import Producto
from ventas.models import Cliente


class OrdenReparacion(models.Model):
    ESTADO = [
        ('recibido',     'Recibido'),        # equipo ingresado, sin revisar
        ('diagnostico',  'En diagnóstico'),  # técnico evaluando
        ('en_proceso',   'En proceso'),      # reparación en curso
        ('esperando',    'Esperando pieza'), # falta una pieza
        ('listo',        'Listo'),           # reparación terminada, por entregar
        ('entregado',    'Entregado'),       # cliente retiró el equipo
        ('sin_reparar',  'Sin reparar'),     # no se pudo reparar o cliente no quiso
    ]
    PRIORIDAD = [
        ('normal',   'Normal'),
        ('urgente',  'Urgente'),
        ('express',  'Express'),
    ]

    numero_or      = models.CharField(max_length=20, unique=True)
    cliente        = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name='reparaciones'
    )
    tecnico        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reparaciones_asignadas'
    )
    recibido_por   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reparaciones_recibidas'
    )

    # Datos del equipo
    tipo_equipo    = models.CharField(max_length=100)          # ej: "Laptop", "PC", "Impresora"
    marca          = models.CharField(max_length=100, blank=True)
    modelo         = models.CharField(max_length=100, blank=True)
    serie          = models.CharField(max_length=100, blank=True)
    descripcion_falla = models.TextField()                     # lo que reporta el cliente
    accesorios     = models.TextField(blank=True)              # cargador, mouse, etc.
    observaciones  = models.TextField(blank=True)              # estado físico al ingresar

    # Trabajo realizado
    diagnostico    = models.TextField(blank=True)              # lo que encontró el técnico
    trabajo_realizado = models.TextField(blank=True)

    estado         = models.CharField(max_length=20, choices=ESTADO, default='recibido')
    prioridad      = models.CharField(max_length=10, choices=PRIORIDAD, default='normal')

    # Costos
    costo_mano_obra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    costo_piezas    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total           = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    fecha_ingreso  = models.DateTimeField(auto_now_add=True)
    fecha_entrega  = models.DateTimeField(null=True, blank=True)  # fecha real de entrega
    fecha_prometida = models.DateField(null=True, blank=True)     # fecha prometida al cliente

    class Meta:
        db_table = 'ordenes_reparacion'
        ordering = ['-fecha_ingreso']

    def __str__(self):
        return f"{self.numero_or} — {self.tipo_equipo} ({self.cliente.nombre})"

    def recalcular_total(self):
        """Recalcula costo_piezas y total desde las piezas usadas."""
        from decimal import Decimal
        costo_piezas = sum(
            p.cantidad * p.precio_unitario for p in self.piezas.all()
        )
        self.costo_piezas = costo_piezas
        self.total = Decimal(str(self.costo_mano_obra)) + costo_piezas
        self.save(update_fields=['costo_piezas', 'total'])


class PiezaUsada(models.Model):
    """
    Pieza del inventario utilizada en una reparación.
    Al guardar descuenta el stock automáticamente.
    """
    orden           = models.ForeignKey(
        OrdenReparacion, on_delete=models.CASCADE, related_name='piezas'
    )
    producto        = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad        = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'piezas_usadas'

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad} → OR {self.orden.numero_or}"


class ComprobanteReparacion(models.Model):
    """Comprobante de cobro propio de la reparación (separado de ventas)."""
    TIPO = [
        ('boleta',  'Boleta'),
        ('factura', 'Factura'),
        ('ticket',  'Ticket'),
    ]
    ESTADO = [
        ('emitido', 'Emitido'),
        ('anulado', 'Anulado'),
    ]

    orden            = models.OneToOneField(
        OrdenReparacion, on_delete=models.PROTECT, related_name='comprobante'
    )
    tipo_comprobante = models.CharField(max_length=10, choices=TIPO, default='ticket')
    serie            = models.CharField(max_length=10)
    numero           = models.CharField(max_length=10)
    monto_total      = models.DecimalField(max_digits=10, decimal_places=2)
    estado           = models.CharField(max_length=10, choices=ESTADO, default='emitido')
    fecha_emision    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'comprobantes_reparacion'
        unique_together = ('tipo_comprobante', 'serie', 'numero')

    def __str__(self):
        return f"{self.tipo_comprobante} {self.serie}-{self.numero}"