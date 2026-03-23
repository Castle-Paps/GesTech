from rest_framework import serializers
from .models import Cliente, MetodoPago, Venta, DetalleVenta, Recibo
from catalogo.models import Producto


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Cliente
        fields = ['id', 'nombre', 'dni_ruc', 'telefono', 'email', 'direccion']


class MetodoPagoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MetodoPago
        fields = ['id', 'nombre', 'activo']


class DetalleVentaSerializer(serializers.ModelSerializer):
    # Muestra el nombre del producto en vez del id
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model  = DetalleVenta
        fields = ['id', 'producto', 'producto_nombre', 'cantidad',
                  'precio_unitario', 'descuento_item', 'subtotal']


class VentaSerializer(serializers.ModelSerializer):
    # Muestra los detalles completos dentro de la venta
    detalles        = DetalleVentaSerializer(many=True, read_only=True)
    cliente_nombre  = serializers.CharField(source='cliente.nombre', read_only=True)
    vendedor_nombre = serializers.CharField(source='vendedor.username', read_only=True)

    class Meta:
        model  = Venta
        fields = ['id', 'numero_venta', 'tipo_venta', 'estado',
                  'cliente', 'cliente_nombre',
                  'vendedor', 'vendedor_nombre',
                  'metodo_pago', 'subtotal', 'descuento',
                  'igv', 'total', 'fecha_venta', 'detalles']


class CrearVentaSerializer(serializers.Serializer):
    # Serializer especial para crear una venta con sus detalles en una sola petición
    cliente        = serializers.IntegerField(required=False, allow_null=True)
    metodo_pago    = serializers.IntegerField(required=False, allow_null=True)
    tipo_venta     = serializers.ChoiceField(choices=['directa', 'ensamblaje', 'reparacion'],
                                             default='directa')
    descuento      = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    detalles       = serializers.ListField(child=serializers.DictField())
    # detalles es una lista de productos con cantidad y precio


class ReciboSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Recibo
        fields = ['id', 'venta', 'tipo_comprobante', 'serie',
                  'numero', 'cliente_nombre', 'monto_total', 'estado', 'fecha_emision']