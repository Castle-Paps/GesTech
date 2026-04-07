from django.urls import path
from .views import (
    CategoriaView, CategoriaDetalleView,
    SubcategoriaView, SubcategoriaDetalleView,
    ProductoView, ProductoDetalleView, ReactivarProductoView,
)

urlpatterns = [
    # Categorías
    path('categorias/',              CategoriaView.as_view(),          name='categorias'),
    path('categorias/<int:pk>/',     CategoriaDetalleView.as_view(),   name='categoria-detalle'),

    # Subcategorías
    path('subcategorias/',           SubcategoriaView.as_view(),       name='subcategorias'),
    path('subcategorias/<int:pk>/',  SubcategoriaDetalleView.as_view(), name='subcategoria-detalle'),

    # Productos
    path('productos/',               ProductoView.as_view(),           name='productos'),
    path('productos/<int:pk>/',      ProductoDetalleView.as_view(),    name='producto-detalle'),
    path('productos/<int:pk>/reactivar/', ReactivarProductoView.as_view(), name='producto-reactivar'),
]