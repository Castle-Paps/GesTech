from rest_framework import serializers
from .models import OrdenReparacion, PiezaUsada, ComprobanteReparacion


class PiezaUsadaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model  = PiezaUsada
        fields = ['id', 'producto', 'producto_nombre', 'cantidad', 'precio_unitario']


class OrdenReparacionSerializer(serializers.ModelSerializer):
    piezas         = PiezaUsadaSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre',   read_only=True)
    tecnico_nombre = serializers.CharField(source='tecnico.username', read_only=True, default='Sin asignar')

    class Meta:
        model  = OrdenReparacion
        fields = [
            'id', 'numero_or', 'estado', 'prioridad',
            'cliente', 'cliente_nombre',
            'tecnico', 'tecnico_nombre',
            'tipo_equipo', 'marca', 'modelo', 'serie',
            'descripcion_falla', 'accesorios', 'observaciones',
            'diagnostico', 'trabajo_realizado',
            'costo_mano_obra', 'costo_piezas', 'total',
            'fecha_ingreso', 'fecha_entrega', 'fecha_prometida',
            'piezas',
        ]


class CrearOrdenReparacionSerializer(serializers.Serializer):
    # Datos del cliente
    cliente          = serializers.IntegerField()

    # Datos del equipo
    tipo_equipo      = serializers.CharField(max_length=100)
    marca            = serializers.CharField(max_length=100, required=False, allow_blank=True)
    modelo           = serializers.CharField(max_length=100, required=False, allow_blank=True)
    serie            = serializers.CharField(max_length=100, required=False, allow_blank=True)
    descripcion_falla = serializers.CharField()
    accesorios       = serializers.CharField(required=False, allow_blank=True)
    observaciones    = serializers.CharField(required=False, allow_blank=True)

    # Asignación y prioridad
    tecnico          = serializers.IntegerField(required=False, allow_null=True)
    prioridad        = serializers.ChoiceField(
        choices=['normal', 'urgente', 'express'], default='normal'
    )
    fecha_prometida  = serializers.DateField(required=False, allow_null=True)
    costo_mano_obra  = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)


class ActualizarOrdenSerializer(serializers.Serializer):
    # Todos opcionales — solo se actualizan los que vienen
    estado           = serializers.ChoiceField(
        choices=['recibido', 'diagnostico', 'en_proceso',
                 'esperando', 'listo', 'entregado', 'sin_reparar'],
        required=False
    )
    tecnico          = serializers.IntegerField(required=False, allow_null=True)
    prioridad        = serializers.ChoiceField(
        choices=['normal', 'urgente', 'express'], required=False
    )
    diagnostico      = serializers.CharField(required=False, allow_blank=True)
    trabajo_realizado = serializers.CharField(required=False, allow_blank=True)
    costo_mano_obra  = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    fecha_prometida  = serializers.DateField(required=False, allow_null=True)
    fecha_entrega    = serializers.DateTimeField(required=False, allow_null=True)


class AgregarPiezaSerializer(serializers.Serializer):
    producto_id     = serializers.IntegerField()
    cantidad        = serializers.IntegerField(min_value=1)
    precio_unitario = serializers.DecimalField(max_digits=10, decimal_places=2)


class ComprobanteReparacionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ComprobanteReparacion
        fields = ['id', 'orden', 'tipo_comprobante', 'serie',
                  'numero', 'monto_total', 'estado', 'fecha_emision']
        
class EmitirComprobanteSerializer(serializers.Serializer):
    tipo_comprobante = serializers.ChoiceField(
        choices=['boleta', 'factura', 'ticket'],
        default='ticket'
    )
    cliente_nombre   = serializers.CharField(max_length=150, required=False, allow_blank=True)