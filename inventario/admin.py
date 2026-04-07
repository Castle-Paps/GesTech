from django.contrib import admin
from django.db import models as django_models
from .models import Inventario, Movimiento


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display   = ('producto', 'stock_actual', 'stock_minimo',
                      'stock_maximo', 'ubicacion', 'bajo_minimo_display', 'ultima_actualizacion')
    search_fields  = ('producto__nombre', 'producto__sku', 'ubicacion')
    list_filter    = ('ubicacion',)
    readonly_fields = ('stock_actual', 'ultima_actualizacion')
    ordering       = ('producto__nombre',)

    def bajo_minimo_display(self, obj):
        return obj.esta_bajo_minimo()
    bajo_minimo_display.short_description = '⚠ Bajo mínimo'
    bajo_minimo_display.boolean = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('producto')


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display  = ('fecha', 'producto', 'tipo', 'cantidad',
                     'stock_antes', 'stock_despues', 'origen_tipo', 'usuario')
    list_filter   = ('tipo', 'origen_tipo')
    search_fields = ('producto__nombre', 'producto__sku', 'usuario__username', 'notas')
    readonly_fields = ('fecha', 'producto', 'usuario', 'tipo', 'cantidad',
                       'stock_antes', 'stock_despues', 'origen_tipo', 'origen_id')
    ordering      = ('-fecha',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('producto', 'usuario')

    def has_add_permission(self, request):
        return False   # Los movimientos solo los crea el sistema

    def has_delete_permission(self, request, obj=None):
        return False   # Los movimientos son inmutables (trazabilidad)