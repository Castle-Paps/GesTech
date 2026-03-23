from django.urls import path
from .views import RegistroView, LoginView, PerfilView, LogoutView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('registro/', RegistroView.as_view(),      name='registro'),
    path('login/',    LoginView.as_view(),          name='login'),
    path('logout/',   LogoutView.as_view(),         name='logout'),
    path('perfil/',   PerfilView.as_view(),         name='perfil'),
    path('refresh/',  TokenRefreshView.as_view(),   name='token_refresh'),
    # refresh/ renueva el token de acceso cuando expira
]