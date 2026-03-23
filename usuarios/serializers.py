from rest_framework import serializers
from .models import Usuario, Rol, Permiso


class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model   = Permiso
        fields  = ['id', 'modulo', 'accion', 'descripcion']


class RolSerializer(serializers.ModelSerializer):
    permisos = PermisoSerializer(many=True, read_only=True)

    class Meta:
        model  = Rol
        fields = ['id', 'nombre', 'descripcion', 'activo', 'permisos']


class UsuarioSerializer(serializers.ModelSerializer):
    roles = RolSerializer(many=True, read_only=True)

    class Meta:
        model  = Usuario
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'activo', 'roles']


class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model  = Usuario
        fields = ['username', 'email', 'password', 'first_name', 'last_name']

    def create(self, validated_data):
        usuario = Usuario.objects.create_user(**validated_data)
        return usuario