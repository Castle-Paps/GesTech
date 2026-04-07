from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import Usuario, Rol
from .serializers import (
    UsuarioSerializer, RegistroSerializer,
    RolSerializer, CrearRolSerializer,
    AsignarRolesSerializer, CambiarPasswordSerializer,
)


# ── Autenticación ─────────────────────────────────────────────────────────────

class RegistroView(APIView):
    """Solo admins pueden crear nuevos usuarios."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = RegistroSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.save()
            return Response({
                'mensaje': 'Usuario creado correctamente',
                'usuario': UsuarioSerializer(usuario).data,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        usuario = authenticate(username=username, password=password)
        if usuario is None:
            return Response(
                {'error': 'Credenciales incorrectas'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Actualizar último acceso
        usuario.ultimo_acceso = timezone.now()
        usuario.save(update_fields=['ultimo_acceso'])

        refresh = RefreshToken.for_user(usuario)
        return Response({
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'usuario': UsuarioSerializer(usuario).data,
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'mensaje': 'Sesión cerrada correctamente'})
        except Exception:
            return Response(
                {'error': 'Token inválido'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PerfilView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    def patch(self, request):
        """El usuario puede editar su propio nombre y email."""
        serializer = UsuarioSerializer(
            request.user, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CambiarPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CambiarPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Verificar que la contraseña actual sea correcta
        if not request.user.check_password(data['password_actual']):
            return Response(
                {'error': 'La contraseña actual es incorrecta'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(data['password_nuevo'])
        request.user.save(update_fields=['password'])
        return Response({'mensaje': 'Contraseña actualizada correctamente'})


# ── Gestión de roles ──────────────────────────────────────────────────────────

class RolListView(APIView):
    """Lista todos los roles / crea uno nuevo. Solo admins."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        roles = Rol.objects.prefetch_related('permisos').all()
        return Response(RolSerializer(roles, many=True).data)

    def post(self, request):
        serializer = CrearRolSerializer(data=request.data)
        if serializer.is_valid():
            rol = serializer.save()
            return Response(RolSerializer(rol).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RolDetalleView(APIView):
    """Ver, editar o desactivar un rol específico. Solo admins."""
    permission_classes = [IsAdminUser]

    def _get(self, pk):
        try:
            return Rol.objects.get(pk=pk), None
        except Rol.DoesNotExist:
            return None, Response(
                {'error': 'Rol no encontrado'}, status=status.HTTP_404_NOT_FOUND
            )

    def get(self, request, pk):
        rol, err = self._get(pk)
        if err: return err
        return Response(RolSerializer(rol).data)

    def patch(self, request, pk):
        rol, err = self._get(pk)
        if err: return err
        serializer = CrearRolSerializer(rol, data=request.data, partial=True)
        if serializer.is_valid():
            return Response(RolSerializer(serializer.save()).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Desactiva el rol en lugar de borrarlo."""
        rol, err = self._get(pk)
        if err: return err
        rol.activo = False
        rol.save(update_fields=['activo'])
        return Response({'mensaje': f'Rol "{rol.nombre}" desactivado'})


class AsignarRolesView(APIView):
    """Asigna (reemplaza) los roles de un usuario. Solo admins."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            usuario = Usuario.objects.get(pk=pk)
        except Usuario.DoesNotExist:
            return Response(
                {'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = AsignarRolesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario.roles.set(serializer.validated_data['rol_ids'])
        return Response({
            'mensaje': f'Roles actualizados para {usuario.username}',
            'usuario': UsuarioSerializer(usuario).data,
        })