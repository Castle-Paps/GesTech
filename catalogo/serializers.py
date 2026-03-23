from rest_framework import serializers
from .models import CategoriaProducto, SubcategoriaProducto, Producto


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CategoriaProducto
        fields = ['id', 'nombre', 'descripcion']


class SubcategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SubcategoriaProducto
        fields = ['id', 'categoria', 'nombre', 'descripcion']


class ProductoSerializer(serializers.ModelSerializer):
    # Muestra el nombre de categoría y subcategoría en vez del id
    categoria_nombre    = serializers.CharField(source='categoria.nombre',    read_only=True)
    subcategoria_nombre = serializers.CharField(source='subcategoria.nombre', read_only=True)

    class Meta:
        model  = Producto
        fields = [
            'id', 'sku', 'nombre', 'marca', 'modelo', 'descripcion',
            'precio_compra', 'precio_venta', 'es_servicio', 'activo',
            'categoria', 'categoria_nombre',
            'subcategoria', 'subcategoria_nombre'
        ]