from rest_framework import serializers
from .models import Proveedor, OrdenCompra, DetalleOrdenCompra, RecepcionCompra, DetalleRecepcion


# ── Proveedores ───────────────────────────────────────────────────────────────

class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Proveedor
        fields = ['id', 'nombre', 'ruc', 'telefono', 'email',
                  'direccion', 'contacto', 'activo', 'creado_en']
        read_only_fields = ['creado_en']


# ── Orden de Compra ───────────────────────────────────────────────────────────

class DetalleOCSerializer(serializers.ModelSerializer):
    producto_nombre   = serializers.CharField(source='producto.nombre', read_only=True)
    producto_sku      = serializers.CharField(source='producto.sku',    read_only=True)
    pendiente_recibir = serializers.SerializerMethodField()

    class Meta:
        model  = DetalleOrdenCompra
        fields = ['id', 'producto', 'producto_nombre', 'producto_sku',
                  'cantidad', 'precio_unitario', 'subtotal',
                  'cantidad_recibida', 'pendiente_recibir']
        read_only_fields = ['subtotal', 'cantidad_recibida']

    def get_pendiente_recibir(self, obj):
        return obj.cantidad - obj.cantidad_recibida


class OrdenCompraSerializer(serializers.ModelSerializer):
    detalles              = DetalleOCSerializer(many=True, read_only=True)
    proveedor_nombre      = serializers.CharField(source='proveedor.nombre',          read_only=True)
    solicitado_por_nombre = serializers.CharField(source='solicitado_por.username',   read_only=True)
    recepciones_count     = serializers.SerializerMethodField()

    class Meta:
        model  = OrdenCompra
        fields = [
            'id', 'numero_oc',
            'proveedor', 'proveedor_nombre',
            'solicitado_por', 'solicitado_por_nombre',
            'estado', 'subtotal', 'igv', 'total',
            'notas', 'fecha_creacion', 'fecha_esperada',
            'recepciones_count', 'detalles',
        ]
        read_only_fields = ['numero_oc', 'solicitado_por', 'subtotal', 'igv', 'total', 'fecha_creacion']

    def get_recepciones_count(self, obj):
        return obj.recepciones.count()


# ── Serializers tipados para crear OC ────────────────────────────────────────

class DetalleOCInputSerializer(serializers.Serializer):
    """Valida cada ítem al crear una Orden de Compra."""
    producto_id     = serializers.IntegerField()
    cantidad        = serializers.IntegerField(min_value=1)
    precio_unitario = serializers.DecimalField(max_digits=10, decimal_places=2)


class CrearOrdenCompraSerializer(serializers.Serializer):
    """Valida el body completo para crear una OC."""
    proveedor      = serializers.IntegerField()
    fecha_esperada = serializers.DateField(required=False, allow_null=True)
    notas          = serializers.CharField(required=False, allow_blank=True, default='')
    detalles       = DetalleOCInputSerializer(many=True)

    def validate_detalles(self, value):
        if not value:
            raise serializers.ValidationError(
                'La orden debe tener al menos un producto.'
            )
        # Verificar que no haya productos duplicados
        ids = [item['producto_id'] for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                'Hay productos duplicados en los detalles.'
            )
        return value


class ActualizarOrdenSerializer(serializers.Serializer):
    """Para cambiar estado o notas de una OC."""
    ESTADOS_VALIDOS = ['borrador', 'enviada', 'anulada']
    estado = serializers.ChoiceField(choices=ESTADOS_VALIDOS, required=False)
    notas  = serializers.CharField(required=False, allow_blank=True)


# ── Recepción de mercancía ────────────────────────────────────────────────────

class DetalleRecepcionSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='detalle_oc.producto.nombre', read_only=True)
    producto_sku    = serializers.CharField(source='detalle_oc.producto.sku',    read_only=True)

    class Meta:
        model  = DetalleRecepcion
        fields = ['id', 'detalle_oc', 'producto_nombre', 'producto_sku', 'cantidad']


class RecepcionCompraSerializer(serializers.ModelSerializer):
    detalles            = DetalleRecepcionSerializer(many=True, read_only=True)
    recibido_por_nombre = serializers.CharField(source='recibido_por.username', read_only=True)
    orden_numero        = serializers.CharField(source='orden.numero_oc',       read_only=True)

    class Meta:
        model  = RecepcionCompra
        fields = ['id', 'orden', 'orden_numero', 'recibido_por',
                  'recibido_por_nombre', 'fecha', 'notas', 'detalles']
        read_only_fields = ['recibido_por', 'fecha']


class ItemRecepcionSerializer(serializers.Serializer):
    """Valida cada ítem al registrar una recepción."""
    detalle_oc_id     = serializers.IntegerField()
    cantidad_recibida = serializers.IntegerField(min_value=1)


class CrearRecepcionSerializer(serializers.Serializer):
    """Valida el body completo para registrar una recepción."""
    orden_id = serializers.IntegerField()
    notas    = serializers.CharField(required=False, allow_blank=True, default='')
    items    = ItemRecepcionSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError(
                'Debes recepcionar al menos un producto.'
            )
        # Verificar que no haya detalles duplicados
        ids = [item['detalle_oc_id'] for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                'Hay detalles de OC duplicados en los items.'
            )
        return value