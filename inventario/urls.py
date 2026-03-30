from django.urls import path
from .views import (InventarioListView, InventarioAlertasView,
                    InventarioDetalleView, AjusteStockView, MovimientoListView)

urlpatterns = [
    # Inventario
    path('',                        InventarioListView.as_view(),    name='inventario'),
    path('alertas/',                InventarioAlertasView.as_view(), name='alertas'),
    path('<int:producto_id>/',      InventarioDetalleView.as_view(), name='inventario-detalle'),
    path('ajuste/',                 AjusteStockView.as_view(),       name='ajuste-stock'),

    # Movimientos
    path('movimientos/',            MovimientoListView.as_view(),    name='movimientos'),
]