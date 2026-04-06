from django.db import models
from django.conf import settings


class CategoriaGasto(models.Model):
    """Tipos de gasto operativo: alquiler, luz, agua, sueldos, etc."""
    nombre      = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'categorias_gasto'

    def __str__(self):
        return self.nombre


class Gasto(models.Model):
    """Gasto operativo del local (no relacionado a compras de inventario)."""
    ESTADO = [
        ('pendiente', 'Pendiente'),
        ('pagado',    'Pagado'),
    ]

    categoria    = models.ForeignKey(
        CategoriaGasto, on_delete=models.PROTECT, related_name='gastos'
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    descripcion  = models.CharField(max_length=255)
    monto        = models.DecimalField(max_digits=12, decimal_places=2)
    estado       = models.CharField(max_length=10, choices=ESTADO, default='pagado')
    fecha        = models.DateField()
    comprobante  = models.CharField(max_length=100, blank=True)  # nro de factura/recibo
    notas        = models.TextField(blank=True)
    creado_en    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gastos'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.categoria.nombre} — S/ {self.monto} ({self.fecha})"


class CajaDiaria(models.Model):
    """
    Registro de apertura y cierre de caja por día.
    Una caja por día por usuario (cajero).
    """
    ESTADO = [
        ('abierta',  'Abierta'),
        ('cerrada',  'Cerrada'),
    ]

    cajero          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cajas'
    )
    fecha           = models.DateField()
    estado          = models.CharField(max_length=10, choices=ESTADO, default='abierta')

    monto_apertura  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_cierre    = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    monto_esperado  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    diferencia      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    notas_apertura  = models.TextField(blank=True)
    notas_cierre    = models.TextField(blank=True)

    hora_apertura   = models.DateTimeField(auto_now_add=True)
    hora_cierre     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table        = 'caja_diaria'
        ordering        = ['-fecha']
        unique_together = ('cajero', 'fecha')  # una caja por cajero por día

    def __str__(self):
        return f"Caja {self.fecha} — {self.cajero.username} ({self.estado})"