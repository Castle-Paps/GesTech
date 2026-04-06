from django.db import models
from usuarios.models import Usuario
from catalogo.models import Producto


class Cliente(models.Model):
    nombre     = models.CharField(max_length=150)
    dni_ruc    = models.CharField(max_length=20, unique=True, null=True, blank=True)
    telefono   = models.CharField(max_length=20, null=True, blank=True)
    email      = models.CharField(max_length=150, null=True, blank=True)
    direccion  = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clientes'

    def __str__(self):
        return self.nombre


class MetodoPago(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'metodos_pago'

    def __str__(self):
        return self.nombre


class Venta(models.Model):
    TIPO_VENTA = [
        ('directa',     'Directa'),
        ('ensamblaje',  'Ensamblaje'),
        ('reparacion',  'Reparación'),
    ]
    ESTADO = [
        ('pendiente',   'Pendiente'),
        ('completada',  'Completada'),
        ('anulada',     'Anulada'),
    ]

    cliente        = models.ForeignKey(Cliente,    on_delete=models.SET_NULL, null=True, blank=True)
    vendedor       = models.ForeignKey(Usuario,    on_delete=models.PROTECT)
    metodo_pago    = models.ForeignKey(MetodoPago, on_delete=models.SET_NULL, null=True, blank=True)
    numero_venta   = models.CharField(max_length=20, unique=True)
    tipo_venta     = models.CharField(max_length=20, choices=TIPO_VENTA, default='directa')
    estado         = models.CharField(max_length=20, choices=ESTADO, default='pendiente')
    subtotal       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuento      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igv            = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fecha_venta    = models.DateTimeField(auto_now_add=True)

    # Campos de Mercado Pago
    mp_preference_id = models.CharField(max_length=255, null=True, blank=True)
    mp_payment_id    = models.CharField(max_length=255, null=True, blank=True)
    mp_status        = models.CharField(max_length=50,  null=True, blank=True)

    class Meta:
        db_table = 'ventas'

    def __str__(self):
        return self.numero_venta


class DetalleVenta(models.Model):
    venta           = models.ForeignKey(Venta,    on_delete=models.CASCADE, related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.PROTECT)
    agrupacion      = models.CharField(max_length=100, null=True, blank=True)
    cantidad        = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    descuento_item  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal        = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'detalle_venta'


class Recibo(models.Model):
    TIPO = [
        ('boleta',  'Boleta'),
        ('factura', 'Factura'),
        ('ticket',  'Ticket'),
    ]
    ESTADO = [
        ('emitido', 'Emitido'),
        ('anulado', 'Anulado'),
    ]
    cliente_nombre = models.CharField(max_length=150, null=True, blank=True)
    venta            = models.OneToOneField(Venta, on_delete=models.PROTECT)
    tipo_comprobante = models.CharField(max_length=10, choices=TIPO)
    serie            = models.CharField(max_length=10)
    numero           = models.CharField(max_length=10)
    fecha_emision    = models.DateTimeField(auto_now_add=True)
    monto_total      = models.DecimalField(max_digits=10, decimal_places=2)
    estado           = models.CharField(max_length=10, choices=ESTADO, default='emitido')

    class Meta:
        db_table = 'recibo'
        # Evita comprobantes duplicados
        unique_together = ('tipo_comprobante', 'serie', 'numero')

    def __str__(self):
        return f"{self.tipo_comprobante} {self.serie}-{self.numero}"
    
    
