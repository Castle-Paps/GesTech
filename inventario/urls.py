from django.urls import path
from .views import (
    InventarioListView, InventarioDetalleView, InventarioAlertasView,
    AjusteStockView,
    MovimientoListView, MovimientoProductoView,
)

urlpatterns = [
    # Inventario general
    path('',                                    InventarioListView.as_view(),    name='inventario'),
    path('alertas/',                            InventarioAlertasView.as_view(), name='alertas'),
    path('ajuste/',                             AjusteStockView.as_view(),       name='ajuste-stock'),

    # Inventario por producto
    path('<int:producto_id>/',                  InventarioDetalleView.as_view(),   name='inventario-detalle'),
    path('<int:producto_id>/movimientos/',      MovimientoProductoView.as_view(),  name='movimientos-producto'),

    # Todos los movimientos
    path('movimientos/',                        MovimientoListView.as_view(),    name='movimientos'),
]