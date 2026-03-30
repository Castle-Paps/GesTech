from rest_framework import serializers
from .models import Inventario, Movimiento


class InventarioSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_sku    = serializers.CharField(source='producto.sku',    read_only=True)
    bajo_minimo     = serializers.SerializerMethodField()

    class Meta:
        model  = Inventario
        fields = ['id', 'producto', 'producto_nombre', 'producto_sku',
                  'stock_actual', 'stock_minimo', 'stock_maximo',
                  'ubicacion', 'ultima_actualizacion', 'bajo_minimo']

    def get_bajo_minimo(self, obj):
        # Indica si el stock está por debajo del mínimo
        return obj.esta_bajo_minimo()


class MovimientoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    usuario_nombre  = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model  = Movimiento
        fields = ['id', 'producto', 'producto_nombre', 'usuario',
                  'usuario_nombre', 'tipo', 'cantidad', 'stock_antes',
                  'stock_despues', 'origen_tipo', 'origen_id', 'fecha', 'notas']