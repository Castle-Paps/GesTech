from django.urls import path
from .views import CategoriaView, SubcategoriaView, ProductoView, ProductoDetalleView

urlpatterns = [
    # Categorías
    path('categorias/',         CategoriaView.as_view(),       name='categorias'),
    path('subcategorias/',      SubcategoriaView.as_view(),    name='subcategorias'),
    
    # Productos
    path('productos/',          ProductoView.as_view(),         name='productos'),
    path('productos/<int:pk>/', ProductoDetalleView.as_view(),  name='producto-detalle'),
]