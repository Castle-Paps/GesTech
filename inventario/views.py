from django.db import models as django_models
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogo.models import Producto
from .models import Inventario, Movimiento
from .serializers import InventarioSerializer, MovimientoSerializer, AjusteStockSerializer
from .services import ajustar_stock


# ── Inventario ────────────────────────────────────────────────────────────────

class InventarioListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista todo el inventario con filtros opcionales:
        ?bajo_minimo=true       → solo productos con stock bajo mínimo
        ?buscar=texto           → filtra por nombre o SKU del producto
        ?ubicacion=texto        → filtra por ubicación
        """
        qs = Inventario.objects.select_related('producto').order_by('producto__nombre')

        bajo_minimo = request.query_params.get('bajo_minimo', '').lower() == 'true'
        buscar      = request.query_params.get('buscar')
        ubicacion   = request.query_params.get('ubicacion')

        if bajo_minimo:
            qs = qs.filter(stock_actual__lte=django_models.F('stock_minimo'))
        if buscar:
            qs = qs.filter(producto__nombre__icontains=buscar) | \
                 qs.filter(producto__sku__icontains=buscar)
        if ubicacion:
            qs = qs.filter(ubicacion__icontains=ubicacion)

        return Response(InventarioSerializer(qs, many=True).data)


class InventarioDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, producto_id):
        try:
            return Inventario.objects.select_related('producto').get(
                producto_id=producto_id
            ), None
        except Inventario.DoesNotExist:
            return None, Response(
                {'error': 'Registro de inventario no encontrado para este producto'},
                status=status.HTTP_404_NOT_FOUND,
            )

    def get(self, request, producto_id):
        inventario, err = self._get(producto_id)
        if err: return err
        return Response(InventarioSerializer(inventario).data)

    def patch(self, request, producto_id):
        """
        Actualiza configuración del inventario: stock_minimo, stock_maximo, ubicacion.
        El stock_actual NO se modifica aquí, solo a través de /ajuste/.
        """
        inventario, err = self._get(producto_id)
        if err: return err

        serializer = InventarioSerializer(inventario, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InventarioAlertasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve todos los productos cuyo stock está en o por debajo del mínimo.
        Útil para el dashboard de alertas.
        """
        qs = Inventario.objects.filter(
            stock_actual__lte=django_models.F('stock_minimo')
        ).select_related('producto').order_by('stock_actual')

        return Response(InventarioSerializer(qs, many=True).data)


class AjusteStockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Ajuste manual de stock por el almacenero.
        Establece el stock al valor exacto indicado y registra el movimiento.

        Body: { "producto_id": 5, "cantidad_nueva": 20, "notas": "Conteo físico" }
        """
        serializer = AjusteStockSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            producto = Producto.objects.get(pk=data['producto_id'], activo=True)
        except Producto.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado o inactivo'},
                status=status.HTTP_404_NOT_FOUND,
            )

        inventario = ajustar_stock(
            producto      = producto,
            cantidad_nueva = data['cantidad_nueva'],
            usuario       = request.user,
            notas         = data.get('notas', ''),
        )
        return Response(InventarioSerializer(inventario).data)


# ── Movimientos ───────────────────────────────────────────────────────────────

class MovimientoListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista movimientos con filtros opcionales:
        ?producto_id=5
        ?tipo=entrada|salida|ajuste
        ?origen_tipo=compra|venta|reparacion|ajuste_manual
        ?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        ?limit=100  (máx 500, default 200)
        """
        qs = Movimiento.objects.select_related(
            'producto', 'usuario'
        ).order_by('-fecha')

        producto_id  = request.query_params.get('producto_id')
        tipo         = request.query_params.get('tipo')
        origen_tipo  = request.query_params.get('origen_tipo')
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin    = request.query_params.get('fecha_fin')
        limit        = min(int(request.query_params.get('limit', 200)), 500)

        if producto_id:
            qs = qs.filter(producto_id=producto_id)
        if tipo:
            qs = qs.filter(tipo=tipo)
        if origen_tipo:
            qs = qs.filter(origen_tipo=origen_tipo)
        if fecha_inicio and fecha_fin:
            qs = qs.filter(fecha__date__range=(fecha_inicio, fecha_fin))

        qs = qs[:limit]

        return Response(MovimientoSerializer(qs, many=True).data)


class MovimientoProductoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, producto_id):
        """
        Historial de movimientos de un producto específico.
        GET /api/inventario/<producto_id>/movimientos/
        """
        try:
            producto = Producto.objects.get(pk=producto_id)
        except Producto.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status=status.HTTP_404_NOT_FOUND,
            )

        movimientos = Movimiento.objects.filter(
            producto=producto
        ).select_related('usuario').order_by('-fecha')

        return Response({
            'producto':    producto.nombre,
            'sku':         producto.sku,
            'movimientos': MovimientoSerializer(movimientos, many=True).data,
        })