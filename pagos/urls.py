from django.urls import path
from . import views

app_name = "pagos"

urlpatterns = [
    path("crear/", views.CrearPagoView.as_view(), name="crear"),
    path("<str:payment_id>/", views.ConsultarPagoView.as_view(), name="consultar"),
    path("webhook/", views.WebhookView.as_view(), name="webhook"),
]