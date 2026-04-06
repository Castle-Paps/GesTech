from django.urls import path
from .views import (
    ProveedorListView, ProveedorDetalleView,
    OrdenCompraListView, OrdenCompraDetalleView,
    RecepcionCompraView, RecepcionListView,
)

urlpatterns = [
    # Proveedores
    path('proveedores/',           ProveedorListView.as_view(),    name='proveedores'),
    path('proveedores/<int:pk>/',  ProveedorDetalleView.as_view(), name='proveedor-detalle'),

    # Órdenes de compra
    path('ordenes/',               OrdenCompraListView.as_view(),   name='ordenes-compra'),
    path('ordenes/<int:pk>/',      OrdenCompraDetalleView.as_view(), name='orden-compra-detalle'),

    # Recepción de mercancía (aumenta el stock automáticamente)
    path('recepciones/',                          RecepcionCompraView.as_view(), name='recepcionar'),
    path('ordenes/<int:orden_id>/recepciones/',   RecepcionListView.as_view(),   name='recepciones-orden'),
]