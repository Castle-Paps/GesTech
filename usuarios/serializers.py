from rest_framework import serializers
from .models import Usuario, Rol, Permiso


class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Permiso
        fields = ['id', 'modulo', 'accion', 'descripcion']


class RolSerializer(serializers.ModelSerializer):
    permisos = PermisoSerializer(many=True, read_only=True)

    class Meta:
        model  = Rol
        fields = ['id', 'nombre', 'descripcion', 'activo', 'permisos']


class CrearRolSerializer(serializers.ModelSerializer):
    """Para crear o editar un rol enviando los IDs de permisos."""
    permiso_ids = serializers.PrimaryKeyRelatedField(
        queryset    = Permiso.objects.all(),
        many        = True,
        write_only  = True,
        required    = False,
        source      = 'permisos',
    )

    class Meta:
        model  = Rol
        fields = ['id', 'nombre', 'descripcion', 'activo', 'permiso_ids']

    def create(self, validated_data):
        permisos = validated_data.pop('permisos', [])
        rol      = Rol.objects.create(**validated_data)
        rol.permisos.set(permisos)
        return rol

    def update(self, instance, validated_data):
        permisos = validated_data.pop('permisos', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if permisos is not None:
            instance.permisos.set(permisos)
        return instance


class UsuarioSerializer(serializers.ModelSerializer):
    roles = RolSerializer(many=True, read_only=True)

    class Meta:
        model  = Usuario
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'activo', 'ultimo_acceso', 'roles']


class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model  = Usuario
        fields = ['username', 'email', 'password', 'first_name', 'last_name']

    def create(self, validated_data):
        return Usuario.objects.create_user(**validated_data)


class AsignarRolesSerializer(serializers.Serializer):
    """Recibe una lista de IDs de roles para asignar a un usuario."""
    rol_ids = serializers.PrimaryKeyRelatedField(
        queryset = Rol.objects.all(),
        many     = True,
    )


class CambiarPasswordSerializer(serializers.Serializer):
    password_actual  = serializers.CharField(write_only=True)
    password_nuevo   = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, min_length=6)

    def validate(self, data):
        if data['password_nuevo'] != data['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Las contraseñas nuevas no coinciden.'}
            )
        return data