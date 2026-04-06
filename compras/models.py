from django.db import models
from django.conf import settings
from catalogo.models import Producto


class Proveedor(models.Model):
    nombre    = models.CharField(max_length=150)
    ruc       = models.CharField(max_length=20, unique=True, null=True, blank=True)
    telefono  = models.CharField(max_length=20, null=True, blank=True)
    email     = models.CharField(max_length=150, null=True, blank=True)
    direccion = models.TextField(null=True, blank=True)
    contacto  = models.CharField(max_length=100, null=True, blank=True)  # nombre del contacto
    activo    = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'proveedores'

    def __str__(self):
        return self.nombre


class OrdenCompra(models.Model):
    ESTADO = [
        ('borrador',   'Borrador'),      # recién creada, aún editable
        ('enviada',    'Enviada'),        # enviada al proveedor
        ('recibida',   'Recibida'),       # mercancía recibida completa
        ('parcial',    'Parcial'),        # mercancía recibida parcialmente
        ('anulada',    'Anulada'),
    ]

    numero_oc      = models.CharField(max_length=20, unique=True)
    proveedor      = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='ordenes')
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    estado         = models.CharField(max_length=10, choices=ESTADO, default='borrador')
    subtotal       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igv            = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notas          = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_esperada = models.DateField(null=True, blank=True)   # fecha esperada de entrega

    class Meta:
        db_table = 'ordenes_compra'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.numero_oc} — {self.proveedor.nombre}"

    def recalcular_totales(self):
        """Recalcula subtotal, IGV y total desde los detalles."""
        from decimal import Decimal
        subtotal = sum(d.subtotal for d in self.detalles.all())
        igv      = subtotal * Decimal('0.18')
        self.subtotal = subtotal
        self.igv      = igv
        self.total    = subtotal + igv
        self.save(update_fields=['subtotal', 'igv', 'total'])


class DetalleOrdenCompra(models.Model):
    orden           = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad        = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal        = models.DecimalField(max_digits=12, decimal_places=2)

    # Cuánto se recibió realmente (se llena al recepcionar)
    cantidad_recibida = models.IntegerField(default=0)

    class Meta:
        db_table = 'detalle_orden_compra'

    def save(self, *args, **kwargs):
        # Calcula el subtotal automáticamente
        from decimal import Decimal
        self.subtotal = Decimal(str(self.precio_unitario)) * self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"


class RecepcionCompra(models.Model):
    """
    Registra la recepción física de mercancía de una orden de compra.
    Puede haber varias recepciones para una misma orden (entregas parciales).
    Al guardar, llama a inventario.services.aumentar_stock automáticamente.
    """
    orden          = models.ForeignKey(OrdenCompra, on_delete=models.PROTECT, related_name='recepciones')
    recibido_por   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha          = models.DateTimeField(auto_now_add=True)
    notas          = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'recepciones_compra'
        ordering = ['-fecha']

    def __str__(self):
        return f"Recepción OC {self.orden.numero_oc} — {self.fecha:%d/%m/%Y}"


class DetalleRecepcion(models.Model):
    """Cada producto recibido dentro de una recepción."""
    recepcion       = models.ForeignKey(RecepcionCompra, on_delete=models.CASCADE, related_name='detalles')
    detalle_oc      = models.ForeignKey(DetalleOrdenCompra, on_delete=models.PROTECT)
    cantidad        = models.IntegerField()

    class Meta:
        db_table = 'detalle_recepcion'

    def __str__(self):
        return f"{self.detalle_oc.producto.nombre} x{self.cantidad}"