from django.db import models


class CategoriaProducto(models.Model):
    nombre      = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'categoria_producto'

    def __str__(self):
        return self.nombre


class SubcategoriaProducto(models.Model):
    # Cada subcategoría pertenece a una categoría principal
    categoria   = models.ForeignKey(
        CategoriaProducto,
        on_delete=models.CASCADE,
        related_name='subcategorias'
    )
    nombre      = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'subcategoria_producto'

    def __str__(self):
        return f"{self.categoria.nombre} - {self.nombre}"


class Producto(models.Model):
    categoria    = models.ForeignKey(
        CategoriaProducto,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    subcategoria = models.ForeignKey(
        SubcategoriaProducto,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    sku           = models.CharField(max_length=50, unique=True)
    nombre        = models.CharField(max_length=150)
    marca         = models.CharField(max_length=100, blank=True, null=True)
    modelo        = models.CharField(max_length=100, blank=True, null=True)
    descripcion   = models.TextField(blank=True, null=True)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_venta  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    es_servicio   = models.BooleanField(default=False)
    activo        = models.BooleanField(default=True)

    class Meta:
        db_table = 'producto'

    def __str__(self):
        return f"{self.sku} - {self.nombre}"