from django.urls import path
from .views import (
    ClienteListView, ClienteDetalleView,
    MetodoPagoView,
    VentaListView, CrearVentaView, VentaDetalleView,
    ReciboView,
    CrearPagoMPView, WebhookMPView,
)

urlpatterns = [
    # Clientes
    path('clientes/',              ClienteListView.as_view(),   name='clientes'),
    path('clientes/<int:pk>/',     ClienteDetalleView.as_view(), name='cliente-detalle'),

    # Métodos de pago
    path('metodos-pago/',          MetodoPagoView.as_view(),    name='metodos-pago'),

    # Ventas
    path('',                       VentaListView.as_view(),     name='ventas'),
    path('crear/',                 CrearVentaView.as_view(),    name='crear-venta'),
    path('<int:pk>/',              VentaDetalleView.as_view(),  name='venta-detalle'),

    # Recibo de una venta
    path('<int:venta_id>/recibo/', ReciboView.as_view(),        name='recibo'),

    # Mercado Pago
    path('<int:venta_id>/pagar/',  CrearPagoMPView.as_view(),   name='crear-pago-mp'),
    path('webhook/',               WebhookMPView.as_view(),     name='webhook-mp'),
]