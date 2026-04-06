from django.contrib import admin
from .models import CategoriaGasto, Gasto, CajaDiaria


@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'descripcion')
    search_fields = ('nombre',)


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display  = ('descripcion', 'categoria', 'monto', 'estado', 'fecha', 'registrado_por')
    list_filter   = ('estado', 'categoria')
    search_fields = ('descripcion', 'comprobante')
    readonly_fields = ('creado_en',)


@admin.register(CajaDiaria)
class CajaDiariaAdmin(admin.ModelAdmin):
    list_display  = ('fecha', 'cajero', 'estado', 'monto_apertura',
                     'monto_cierre', 'monto_esperado', 'diferencia')
    list_filter   = ('estado',)
    readonly_fields = ('hora_apertura', 'hora_cierre', 'monto_esperado', 'diferencia')