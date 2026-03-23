from django.urls import path
from .views import (ClienteView, MetodoPagoView, CrearVentaView,
                    VentaListView, VentaDetalleView, ReciboView)

urlpatterns = [
    # Clientes
    path('clientes/',              ClienteView.as_view(),      name='clientes'),
    
    # Métodos de pago
    path('metodos-pago/',          MetodoPagoView.as_view(),   name='metodos-pago'),
    
    # Ventas
    path('',                       VentaListView.as_view(),    name='ventas'),
    path('crear/',                 CrearVentaView.as_view(),   name='crear-venta'),
    path('<int:pk>/',              VentaDetalleView.as_view(), name='venta-detalle'),
    
    # Recibo
    path('<int:venta_id>/recibo/', ReciboView.as_view(),       name='recibo'),
]