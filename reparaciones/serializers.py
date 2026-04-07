from rest_framework import serializers
from django.db.models import Max
from .models import OrdenReparacion, PiezaUsada, ComprobanteReparacion


# ── Piezas ────────────────────────────────────────────────────────────────────

class PiezaUsadaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_sku    = serializers.CharField(source='producto.sku',    read_only=True)

    class Meta:
        model  = PiezaUsada
        fields = ['id', 'producto', 'producto_nombre', 'producto_sku',
                  'cantidad', 'precio_unitario']


# ── Comprobante ───────────────────────────────────────────────────────────────

class ComprobanteReparacionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ComprobanteReparacion
        fields = ['id', 'orden', 'tipo_comprobante', 'serie',
                  'numero', 'monto_total', 'estado', 'fecha_emision']


# ── Orden de Reparación ───────────────────────────────────────────────────────

class OrdenReparacionSerializer(serializers.ModelSerializer):
    piezas              = PiezaUsadaSerializer(many=True, read_only=True)
    comprobante         = ComprobanteReparacionSerializer(read_only=True)
    cliente_nombre      = serializers.CharField(source='cliente.nombre',        read_only=True)
    tecnico_nombre      = serializers.SerializerMethodField()
    recibido_por_nombre = serializers.CharField(source='recibido_por.username', read_only=True)

    class Meta:
        model  = OrdenReparacion
        fields = [
            'id', 'numero_or', 'estado', 'prioridad',
            'cliente', 'cliente_nombre',
            'tecnico', 'tecnico_nombre',
            'recibido_por', 'recibido_por_nombre',
            'tipo_equipo', 'marca', 'modelo', 'serie',
            'descripcion_falla', 'accesorios', 'observaciones',
            'diagnostico', 'trabajo_realizado',
            'costo_mano_obra', 'costo_piezas', 'total',
            'fecha_ingreso', 'fecha_entrega', 'fecha_prometida',
            'piezas', 'comprobante',
        ]

    def get_tecnico_nombre(self, obj):
        return obj.tecnico.username if obj.tecnico else None


# ── Serializers de entrada ────────────────────────────────────────────────────

class CrearOrdenReparacionSerializer(serializers.Serializer):
    # Cliente
    cliente           = serializers.IntegerField()
    # Equipo
    tipo_equipo       = serializers.CharField(max_length=100)
    marca             = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    modelo            = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    serie             = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    descripcion_falla = serializers.CharField()
    accesorios        = serializers.CharField(required=False, allow_blank=True, default='')
    observaciones     = serializers.CharField(required=False, allow_blank=True, default='')
    # Asignación
    tecnico_id        = serializers.IntegerField(required=False, allow_null=True)
    prioridad         = serializers.ChoiceField(
        choices=['normal', 'urgente', 'express'], default='normal'
    )
    fecha_prometida   = serializers.DateField(required=False, allow_null=True)
    costo_mano_obra   = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0
    )


class ActualizarOrdenSerializer(serializers.Serializer):
    """Todos los campos son opcionales — solo se actualizan los que vienen."""
    ESTADOS = ['recibido', 'diagnostico', 'en_proceso',
               'esperando', 'listo', 'entregado', 'sin_reparar']

    estado            = serializers.ChoiceField(choices=ESTADOS, required=False)
    tecnico_id        = serializers.IntegerField(required=False, allow_null=True)
    prioridad         = serializers.ChoiceField(
        choices=['normal', 'urgente', 'express'], required=False
    )
    diagnostico       = serializers.CharField(required=False, allow_blank=True)
    trabajo_realizado = serializers.CharField(required=False, allow_blank=True)
    costo_mano_obra   = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    fecha_prometida   = serializers.DateField(required=False, allow_null=True)
    observaciones     = serializers.CharField(required=False, allow_blank=True)


class AgregarPiezaSerializer(serializers.Serializer):
    producto_id     = serializers.IntegerField()
    cantidad        = serializers.IntegerField(min_value=1)
    # Opcional: si no se manda, se usa el precio_compra del producto
    precio_unitario = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )


class EmitirComprobanteSerializer(serializers.Serializer):
    tipo_comprobante = serializers.ChoiceField(
        choices=['boleta', 'factura', 'ticket'], default='ticket'
    )


def siguiente_numero_comprobante(tipo: str, serie: str) -> str:
    """Genera el siguiente número correlativo de forma segura."""
    from .models import ComprobanteReparacion
    ultimo = (
        ComprobanteReparacion.objects
        .select_for_update()
        .filter(tipo_comprobante=tipo, serie=serie)
        .aggregate(max_num=Max('numero'))['max_num']
    )
    siguiente = (int(ultimo) + 1) if ultimo else 1
    return str(siguiente).zfill(8)