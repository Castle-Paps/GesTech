from django.contrib import admin
from .models import Usuario, Rol, Permiso


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display  = ('modulo', 'accion', 'descripcion')
    search_fields = ('modulo', 'accion')
    ordering      = ('modulo', 'accion')


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display      = ('nombre', 'activo', 'descripcion')
    search_fields     = ('nombre',)
    filter_horizontal = ('permisos',)
    list_filter       = ('activo',)


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display      = ('username', 'email', 'first_name', 'last_name', 'activo', 'ultimo_acceso')
    search_fields     = ('username', 'email', 'first_name', 'last_name')
    filter_horizontal = ('roles',)
    list_filter       = ('activo', 'is_staff')
    readonly_fields   = ('ultimo_acceso', 'last_login', 'date_joined')