from django.urls import path
from .views import (
    OrdenReparacionListView,
    OrdenReparacionDetalleView,
    PiezaUsadaView,
    ComprobanteReparacionView,
)

urlpatterns = [
    # Órdenes de reparación
    path('',                                    OrdenReparacionListView.as_view(),   name='reparaciones'),
    path('<int:pk>/',                           OrdenReparacionDetalleView.as_view(), name='reparacion-detalle'),

    # Piezas usadas en la reparación (agrega/quita y mueve stock)
    path('<int:pk>/piezas/',                    PiezaUsadaView.as_view(),            name='agregar-pieza'),
    path('<int:pk>/piezas/<int:pieza_id>/',     PiezaUsadaView.as_view(),            name='quitar-pieza'),

    # Comprobante de cobro propio de la reparación
    path('<int:pk>/comprobante/',               ComprobanteReparacionView.as_view(), name='comprobante-reparacion'),
]