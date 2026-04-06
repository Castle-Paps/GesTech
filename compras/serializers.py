from rest_framework import serializers
from .models import Proveedor, OrdenCompra, DetalleOrdenCompra, RecepcionCompra, DetalleRecepcion


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Proveedor
        fields = ['id', 'nombre', 'ruc', 'telefono', 'email',
                  'direccion', 'contacto', 'activo']


# ─── Orden de Compra ──────────────────────────────────────────────────────────

class DetalleOCSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_sku    = serializers.CharField(source='producto.sku',    read_only=True)

    class Meta:
        model  = DetalleOrdenCompra
        fields = ['id', 'producto', 'producto_nombre', 'producto_sku',
                  'cantidad', 'precio_unitario', 'subtotal', 'cantidad_recibida']
        read_only_fields = ['subtotal', 'cantidad_recibida']


class OrdenCompraSerializer(serializers.ModelSerializer):
    detalles            = DetalleOCSerializer(many=True, read_only=True)
    proveedor_nombre    = serializers.CharField(source='proveedor.nombre',          read_only=True)
    solicitado_por_nombre = serializers.CharField(source='solicitado_por.username', read_only=True)

    class Meta:
        model  = OrdenCompra
        fields = ['id', 'numero_oc', 'proveedor', 'proveedor_nombre',
                  'solicitado_por', 'solicitado_por_nombre', 'estado',
                  'subtotal', 'igv', 'total', 'notas',
                  'fecha_creacion', 'fecha_esperada', 'detalles']
        read_only_fields = ['numero_oc', 'solicitado_por', 'subtotal', 'igv', 'total']


class CrearOrdenCompraSerializer(serializers.Serializer):
    """Para crear una OC con sus detalles en una sola petición."""
    proveedor      = serializers.IntegerField()
    fecha_esperada = serializers.DateField(required=False, allow_null=True)
    notas          = serializers.CharField(required=False, allow_blank=True, default='')
    detalles       = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        error_messages={'min_length': 'La orden debe tener al menos un producto.'}
    )
    # Cada item de detalles debe tener: producto_id, cantidad, precio_unitario


# ─── Recepción ────────────────────────────────────────────────────────────────

class DetalleRecepcionSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='detalle_oc.producto.nombre', read_only=True)

    class Meta:
        model  = DetalleRecepcion
        fields = ['id', 'detalle_oc', 'producto_nombre', 'cantidad']


class RecepcionCompraSerializer(serializers.ModelSerializer):
    detalles           = DetalleRecepcionSerializer(many=True, read_only=True)
    recibido_por_nombre = serializers.CharField(source='recibido_por.username', read_only=True)

    class Meta:
        model  = RecepcionCompra
        fields = ['id', 'orden', 'recibido_por', 'recibido_por_nombre',
                  'fecha', 'notas', 'detalles']
        read_only_fields = ['recibido_por', 'fecha']


class CrearRecepcionSerializer(serializers.Serializer):
    """Para registrar la recepción de mercancía."""
    orden_id = serializers.IntegerField()
    notas    = serializers.CharField(required=False, allow_blank=True, default='')
    items    = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        error_messages={'min_length': 'Debes recepcionar al menos un producto.'}
    )
    # Cada item: detalle_oc_id, cantidad_recibida