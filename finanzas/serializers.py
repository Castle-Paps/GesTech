from rest_framework import serializers
from .models import CategoriaGasto, Gasto, CajaDiaria


class CategoriaGastoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CategoriaGasto
        fields = ['id', 'nombre', 'descripcion']


class GastoSerializer(serializers.ModelSerializer):
    categoria_nombre      = serializers.CharField(source='categoria.nombre',        read_only=True)
    registrado_por_nombre = serializers.CharField(source='registrado_por.username', read_only=True)

    class Meta:
        model  = Gasto
        fields = ['id', 'categoria', 'categoria_nombre', 'registrado_por',
                  'registrado_por_nombre', 'descripcion', 'monto', 'estado',
                  'fecha', 'comprobante', 'notas', 'creado_en']
        read_only_fields = ['registrado_por', 'creado_en']


class CrearGastoSerializer(serializers.Serializer):
    categoria_id = serializers.IntegerField()
    descripcion  = serializers.CharField(max_length=255)
    monto        = serializers.DecimalField(max_digits=12, decimal_places=2)
    estado       = serializers.ChoiceField(choices=['pendiente', 'pagado'], default='pagado')
    fecha        = serializers.DateField()
    comprobante  = serializers.CharField(max_length=100, required=False, default='')
    notas        = serializers.CharField(required=False, default='')


# ─── Caja Diaria ──────────────────────────────────────────────────────────────

class CajaDiariaSerializer(serializers.ModelSerializer):
    cajero_nombre = serializers.CharField(source='cajero.username', read_only=True)

    class Meta:
        model  = CajaDiaria
        fields = ['id', 'cajero', 'cajero_nombre', 'fecha', 'estado',
                  'monto_apertura', 'monto_cierre', 'monto_esperado',
                  'diferencia', 'notas_apertura', 'notas_cierre',
                  'hora_apertura', 'hora_cierre']
        read_only_fields = ['cajero', 'fecha', 'monto_esperado',
                            'diferencia', 'hora_apertura', 'hora_cierre']


class AbrirCajaSerializer(serializers.Serializer):
    monto_apertura = serializers.DecimalField(max_digits=12, decimal_places=2)
    notas_apertura = serializers.CharField(required=False, default='')


class CerrarCajaSerializer(serializers.Serializer):
    monto_cierre  = serializers.DecimalField(max_digits=12, decimal_places=2)
    notas_cierre  = serializers.CharField(required=False, default='')