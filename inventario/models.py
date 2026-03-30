from django.db import models
from catalogo.models import Producto
from usuarios.models import Usuario


class Inventario(models.Model):
    # Un registro de inventario por producto
    producto             = models.OneToOneField(Producto, on_delete=models.CASCADE)
    stock_actual         = models.IntegerField(default=0)
    stock_minimo         = models.IntegerField(default=0)
    stock_maximo         = models.IntegerField(null=True, blank=True)
    ubicacion            = models.CharField(max_length=100, null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventario'

    def __str__(self):
        return f"{self.producto.nombre} - Stock: {self.stock_actual}"

    def esta_bajo_minimo(self):
        # Devuelve True si el stock está por debajo del mínimo
        return self.stock_actual <= self.stock_minimo


class Movimiento(models.Model):
    TIPO = [
        ('entrada', 'Entrada'),
        ('salida',  'Salida'),
        ('ajuste',  'Ajuste'),
    ]
    ORIGEN = [
        ('compra',         'Compra'),
        ('venta',          'Venta'),
        ('reparacion',     'Reparación'),
        ('ajuste_manual',  'Ajuste Manual'),
    ]

    producto      = models.ForeignKey(Producto, on_delete=models.PROTECT)
    usuario       = models.ForeignKey(Usuario,  on_delete=models.PROTECT)
    tipo          = models.CharField(max_length=10, choices=TIPO)
    cantidad      = models.IntegerField()
    stock_antes   = models.IntegerField()
    stock_despues = models.IntegerField()
    origen_tipo   = models.CharField(max_length=20, choices=ORIGEN, null=True, blank=True)
    origen_id     = models.IntegerField(null=True, blank=True)
    fecha         = models.DateTimeField(auto_now_add=True)
    notas         = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'movimientos'

    def __str__(self):
        return f"{self.tipo} - {self.producto.nombre} ({self.cantidad})"