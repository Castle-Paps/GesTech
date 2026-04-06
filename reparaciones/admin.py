from django.contrib import admin
from .models import OrdenReparacion, PiezaUsada, ComprobanteReparacion


class PiezaUsadaInline(admin.TabularInline):
    model  = PiezaUsada
    extra  = 0
    readonly_fields = ('precio_unitario',)


@admin.register(OrdenReparacion)
class OrdenReparacionAdmin(admin.ModelAdmin):
    list_display  = ('numero_or', 'cliente', 'tipo_equipo', 'estado',
                     'prioridad', 'tecnico', 'total', 'fecha_ingreso')
    list_filter   = ('estado', 'prioridad')
    search_fields = ('numero_or', 'cliente__nombre', 'serie')
    readonly_fields = ('numero_or', 'costo_piezas', 'total',
                       'fecha_ingreso', 'fecha_entrega')
    inlines       = [PiezaUsadaInline]


@admin.register(ComprobanteReparacion)
class ComprobanteReparacionAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'orden', 'monto_total', 'estado', 'fecha_emision')
    list_filter   = ('tipo_comprobante', 'estado')
    readonly_fields = ('serie', 'numero', 'monto_total', 'fecha_emision')