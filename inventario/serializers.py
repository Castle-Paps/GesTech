from rest_framework import serializers
from .models import Inventario, Movimiento


class InventarioSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_sku    = serializers.CharField(source='producto.sku',    read_only=True)
    bajo_minimo     = serializers.SerializerMethodField()

    class Meta:
        model  = Inventario
        fields = [
            'id', 'producto', 'producto_nombre', 'producto_sku',
            'stock_actual', 'stock_minimo', 'stock_maximo',
            'ubicacion', 'ultima_actualizacion', 'bajo_minimo',
        ]
        # stock_actual solo lo modifica el sistema (servicios), nunca directo por API
        read_only_fields = ['id', 'producto', 'stock_actual', 'ultima_actualizacion']

    def get_bajo_minimo(self, obj):
        return obj.esta_bajo_minimo()

    def validate(self, data):
        stock_min = data.get('stock_minimo')
        stock_max = data.get('stock_maximo')

        # Si se mandan ambos, verificar que min < max
        if stock_min is not None and stock_max is not None:
            if stock_min > stock_max:
                raise serializers.ValidationError(
                    'El stock mínimo no puede ser mayor que el stock máximo.'
                )

        # Si solo viene uno, comparar contra el valor existente
        instance = self.instance
        if instance:
            min_val = stock_min if stock_min is not None else instance.stock_minimo
            max_val = stock_max if stock_max is not None else instance.stock_maximo
            if max_val is not None and min_val > max_val:
                raise serializers.ValidationError(
                    'El stock mínimo no puede ser mayor que el stock máximo.'
                )
        return data


class MovimientoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_sku    = serializers.CharField(source='producto.sku',    read_only=True)
    usuario_nombre  = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model  = Movimiento
        fields = [
            'id', 'producto', 'producto_nombre', 'producto_sku',
            'usuario', 'usuario_nombre',
            'tipo', 'cantidad', 'stock_antes', 'stock_despues',
            'origen_tipo', 'origen_id', 'fecha', 'notas',
        ]


class AjusteStockSerializer(serializers.Serializer):
    """Valida el body del ajuste manual de stock."""
    producto_id    = serializers.IntegerField()
    cantidad_nueva = serializers.IntegerField(min_value=0)
    notas          = serializers.CharField(required=False, allow_blank=True, default='')