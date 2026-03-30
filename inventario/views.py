from django.shortcuts import render

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import Inventario, Movimiento
from .serializers import InventarioSerializer, MovimientoSerializer
from .services import ajustar_stock
from catalogo.models import Producto
from django.db import models

class InventarioListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Lista todo el inventario
        inventario = Inventario.objects.all().select_related('producto')
        serializer = InventarioSerializer(inventario, many=True)
        return Response(serializer.data)


class InventarioAlertasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Solo productos con stock bajo el mínimo
        inventario = Inventario.objects.filter(
            stock_actual__lte=models.F('stock_minimo')
        ).select_related('producto')
        serializer = InventarioSerializer(inventario, many=True)
        return Response(serializer.data)


class InventarioDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, producto_id):
        try:
            inventario = Inventario.objects.get(producto_id=producto_id)
            serializer = InventarioSerializer(inventario)
            return Response(serializer.data)
        except Inventario.DoesNotExist:
            return Response({'error': 'Inventario no encontrado'},
                            status=status.HTTP_404_NOT_FOUND)

    def put(self, request, producto_id):
        # Actualiza stock mínimo, máximo y ubicación
        try:
            inventario = Inventario.objects.get(producto_id=producto_id)
            serializer = InventarioSerializer(inventario, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Inventario.DoesNotExist:
            return Response({'error': 'Inventario no encontrado'},
                            status=status.HTTP_404_NOT_FOUND)


class AjusteStockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Ajuste manual de stock por el almacenero
        producto_id  = request.data.get('producto_id')
        cantidad     = request.data.get('cantidad')
        notas        = request.data.get('notas', '')

        if not producto_id or cantidad is None:
            return Response({'error': 'producto_id y cantidad son requeridos'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            producto = Producto.objects.get(pk=producto_id)
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'},
                            status=status.HTTP_404_NOT_FOUND)

        inventario = ajustar_stock(
            producto      = producto,
            cantidad_nueva = int(cantidad),
            usuario       = request.user,
            notas         = notas,
        )

        return Response(InventarioSerializer(inventario).data)


class MovimientoListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Lista todos los movimientos, el más reciente primero
        movimientos = Movimiento.objects.all().order_by('-fecha').select_related('producto', 'usuario')
        serializer  = MovimientoSerializer(movimientos, many=True)
        return Response(serializer.data)