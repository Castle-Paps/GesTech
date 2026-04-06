from django.contrib import admin
from .models import Proveedor, OrdenCompra, DetalleOrdenCompra, RecepcionCompra, DetalleRecepcion


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'ruc', 'telefono', 'email', 'activo')
    list_filter   = ('activo',)
    search_fields = ('nombre', 'ruc')


class DetalleOCInline(admin.TabularInline):
    model  = DetalleOrdenCompra
    extra  = 0
    readonly_fields = ('subtotal', 'cantidad_recibida')


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display  = ('numero_oc', 'proveedor', 'estado', 'total', 'fecha_creacion')
    list_filter   = ('estado',)
    search_fields = ('numero_oc', 'proveedor__nombre')
    readonly_fields = ('numero_oc', 'subtotal', 'igv', 'total', 'fecha_creacion')
    inlines       = [DetalleOCInline]


class DetalleRecepcionInline(admin.TabularInline):
    model = DetalleRecepcion
    extra = 0


@admin.register(RecepcionCompra)
class RecepcionCompraAdmin(admin.ModelAdmin):
    list_display  = ('orden', 'recibido_por', 'fecha')
    readonly_fields = ('fecha',)
    inlines       = [DetalleRecepcionInline]