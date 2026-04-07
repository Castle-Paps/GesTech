from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegistroView, LoginView, LogoutView, PerfilView,
    CambiarPasswordView,
    RolListView, RolDetalleView, AsignarRolesView,
)

urlpatterns = [
    # Autenticación
    path('registro/',         RegistroView.as_view(),       name='registro'),
    path('login/',            LoginView.as_view(),           name='login'),
    path('logout/',           LogoutView.as_view(),          name='logout'),
    path('refresh/',          TokenRefreshView.as_view(),    name='token_refresh'),

    # Perfil del usuario autenticado
    path('perfil/',           PerfilView.as_view(),          name='perfil'),
    path('perfil/password/',  CambiarPasswordView.as_view(), name='cambiar_password'),

    # Gestión de roles (solo admins)
    path('roles/',            RolListView.as_view(),         name='rol_list'),
    path('roles/<int:pk>/',   RolDetalleView.as_view(),      name='rol_detalle'),

    # Asignar roles a un usuario (solo admins)
    path('<int:pk>/roles/',   AsignarRolesView.as_view(),    name='asignar_roles'),
]