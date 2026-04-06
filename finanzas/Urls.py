from django.urls import path
from .views import (
    CategoriaGastoView,
    GastoListView, GastoDetalleView,
    AbrirCajaView, CerrarCajaView, CajaListView, CajaActivaView,
    ReporteIngresosView, ReporteEgresosView, ReporteResumenView,
)

urlpatterns = [
    # Categorías de gasto
    path('categorias/',              CategoriaGastoView.as_view(),  name='categorias-gasto'),

    # Gastos operativos
    path('gastos/',                  GastoListView.as_view(),       name='gastos'),
    path('gastos/<int:pk>/',         GastoDetalleView.as_view(),    name='gasto-detalle'),

    # Caja diaria
    path('caja/',                    CajaListView.as_view(),        name='cajas'),
    path('caja/activa/',             CajaActivaView.as_view(),      name='caja-activa'),
    path('caja/abrir/',              AbrirCajaView.as_view(),       name='abrir-caja'),
    path('caja/<int:pk>/cerrar/',    CerrarCajaView.as_view(),      name='cerrar-caja'),

    # Reportes financieros
    path('reportes/ingresos/',       ReporteIngresosView.as_view(), name='reporte-ingresos'),
    path('reportes/egresos/',        ReporteEgresosView.as_view(),  name='reporte-egresos'),
    path('reportes/resumen/',        ReporteResumenView.as_view(),  name='reporte-resumen'),
]