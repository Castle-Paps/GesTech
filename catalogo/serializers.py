from rest_framework import serializers
from .models import CategoriaProducto, SubcategoriaProducto, Producto


class CategoriaSerializer(serializers.ModelSerializer):
    # Cuántas subcategorías tiene (útil en el frontend)
    total_subcategorias = serializers.IntegerField(
        source='subcategorias.count', read_only=True
    )

    class Meta:
        model  = CategoriaProducto
        fields = ['id', 'nombre', 'descripcion', 'total_subcategorias']


class SubcategoriaSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)

    class Meta:
        model  = SubcategoriaProducto
        fields = ['id', 'categoria', 'categoria_nombre', 'nombre', 'descripcion']


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

    def validate(self, data):
        """
        Valida que la subcategoría pertenezca a la categoría indicada.
        Funciona tanto en creación (POST) como en edición parcial (PATCH).
        """
        # En PATCH los campos pueden venir incompletos; usamos el valor actual si no viene
        categoria    = data.get('categoria',    getattr(self.instance, 'categoria',    None))
        subcategoria = data.get('subcategoria', getattr(self.instance, 'subcategoria', None))

        if subcategoria and categoria:
            if subcategoria.categoria_id != categoria.id:
                raise serializers.ValidationError(
                    {'subcategoria': (
                        f'La subcategoría "{subcategoria.nombre}" no pertenece '
                        f'a la categoría "{categoria.nombre}".'
                    )}
                )

        return data