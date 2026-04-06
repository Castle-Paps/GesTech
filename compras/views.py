import uuid
from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import (Proveedor, OrdenCompra, DetalleOrdenCompra,
                     RecepcionCompra, DetalleRecepcion)
from .serializers import (ProveedorSerializer, OrdenCompraSerializer,
                          CrearOrdenCompraSerializer, RecepcionCompraSerializer,
                          CrearRecepcionSerializer)
from catalogo.models import Producto
from inventario.services import aumentar_stock


# ─── Proveedores ──────────────────────────────────────────────────────────────

class ProveedorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        proveedores = Proveedor.objects.filter(activo=True)
        return Response(ProveedorSerializer(proveedores, many=True).data)

    def post(self, request):
        serializer = ProveedorSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProveedorDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Proveedor.objects.get(pk=pk), None
        except Proveedor.DoesNotExist:
            return None, Response({'error': 'Proveedor no encontrado'},
                                  status=status.HTTP_404_NOT_FOUND)

    def get(self, request, pk):
        proveedor, err = self._get(pk)
        if err: return err
        return Response(ProveedorSerializer(proveedor).data)

    def put(self, request, pk):
        proveedor, err = self._get(pk)
        if err: return err
        serializer = ProveedorSerializer(proveedor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        proveedor, err = self._get(pk)
        if err: return err
        proveedor.activo = False   # borrado lógico
        proveedor.save(update_fields=['activo'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Órdenes de Compra ────────────────────────────────────────────────────────

class OrdenCompraListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ordenes = OrdenCompra.objects.all().select_related('proveedor', 'solicitado_por')
        return Response(OrdenCompraSerializer(ordenes, many=True).data)

    @transaction.atomic
    def post(self, request):
        """Crea una orden de compra con todos sus detalles en una sola llamada."""
        serializer = CrearOrdenCompraSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Validar proveedor
        try:
            proveedor = Proveedor.objects.get(pk=data['proveedor'], activo=True)
        except Proveedor.DoesNotExist:
            return Response({'error': 'Proveedor no encontrado'},
                            status=status.HTTP_404_NOT_FOUND)

        # Validar y preparar los items
        items      = []
        subtotal   = Decimal('0')

        for item in data['detalles']:
            producto_id     = item.get('producto_id')
            cantidad        = item.get('cantidad')
            precio_unitario = item.get('precio_unitario')

            if not all([producto_id, cantidad, precio_unitario]):
                return Response(
                    {'error': 'Cada detalle requiere producto_id, cantidad y precio_unitario'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                producto = Producto.objects.get(pk=producto_id, activo=True)
            except Producto.DoesNotExist:
                return Response({'error': f'Producto {producto_id} no encontrado'},
                                status=status.HTTP_404_NOT_FOUND)

            cantidad        = int(cantidad)
            precio_unitario = Decimal(str(precio_unitario))
            subtotal_item   = precio_unitario * cantidad
            subtotal       += subtotal_item

            items.append({
                'producto':        producto,
                'cantidad':        cantidad,
                'precio_unitario': precio_unitario,
                'subtotal':        subtotal_item,
            })

        igv   = subtotal * Decimal('0.18')
        total = subtotal + igv

        # Crear la orden
        numero_oc = f"OC-{uuid.uuid4().hex[:8].upper()}"
        orden = OrdenCompra.objects.create(
            numero_oc      = numero_oc,
            proveedor      = proveedor,
            solicitado_por = request.user,
            subtotal       = subtotal,
            igv            = igv,
            total          = total,
            notas          = data.get('notas', ''),
            fecha_esperada = data.get('fecha_esperada'),
        )

        for item in items:
            DetalleOrdenCompra.objects.create(
                orden           = orden,
                producto        = item['producto'],
                cantidad        = item['cantidad'],
                precio_unitario = item['precio_unitario'],
                subtotal        = item['subtotal'],
            )

        return Response(OrdenCompraSerializer(orden).data, status=status.HTTP_201_CREATED)


class OrdenCompraDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return OrdenCompra.objects.get(pk=pk), None
        except OrdenCompra.DoesNotExist:
            return None, Response({'error': 'Orden no encontrada'},
                                  status=status.HTTP_404_NOT_FOUND)

    def get(self, request, pk):
        orden, err = self._get(pk)
        if err: return err
        return Response(OrdenCompraSerializer(orden).data)

    def patch(self, request, pk):
        """Permite cambiar el estado o las notas de la orden."""
        orden, err = self._get(pk)
        if err: return err

        if orden.estado == 'anulada':
            return Response({'error': 'No se puede modificar una orden anulada'},
                            status=status.HTTP_400_BAD_REQUEST)

        nuevo_estado = request.data.get('estado')
        notas        = request.data.get('notas')

        if nuevo_estado:
            estados_validos = [e[0] for e in OrdenCompra.ESTADO]
            if nuevo_estado not in estados_validos:
                return Response({'error': f'Estado inválido. Opciones: {estados_validos}'},
                                status=status.HTTP_400_BAD_REQUEST)
            orden.estado = nuevo_estado

        if notas is not None:
            orden.notas = notas

        orden.save()
        return Response(OrdenCompraSerializer(orden).data)


# ─── Recepción de mercancía ───────────────────────────────────────────────────

class RecepcionCompraView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """
        Registra la recepción de mercancía y actualiza el stock automáticamente.

        Body:
        {
            "orden_id": 5,
            "notas": "Llegó en buen estado",
            "items": [
                {"detalle_oc_id": 12, "cantidad_recibida": 10},
                {"detalle_oc_id": 13, "cantidad_recibida": 5}
            ]
        }
        """
        serializer = CrearRecepcionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Validar la orden
        try:
            orden = OrdenCompra.objects.get(pk=data['orden_id'])
        except OrdenCompra.DoesNotExist:
            return Response({'error': 'Orden de compra no encontrada'},
                            status=status.HTTP_404_NOT_FOUND)

        if orden.estado == 'anulada':
            return Response({'error': 'No se puede recepcionar una orden anulada'},
                            status=status.HTTP_400_BAD_REQUEST)

        if orden.estado == 'recibida':
            return Response({'error': 'Esta orden ya fue recibida completamente'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Crear la recepción
        recepcion = RecepcionCompra.objects.create(
            orden        = orden,
            recibido_por = request.user,
            notas        = data.get('notas', ''),
        )

        items_procesados = []

        for item in data['items']:
            detalle_oc_id    = item.get('detalle_oc_id')
            cantidad_recibida = int(item.get('cantidad_recibida', 0))

            if not detalle_oc_id or cantidad_recibida <= 0:
                return Response(
                    {'error': 'Cada item requiere detalle_oc_id y cantidad_recibida > 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                detalle_oc = DetalleOrdenCompra.objects.get(pk=detalle_oc_id, orden=orden)
            except DetalleOrdenCompra.DoesNotExist:
                return Response(
                    {'error': f'Detalle {detalle_oc_id} no pertenece a esta orden'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # No permitir recibir más de lo pedido
            pendiente = detalle_oc.cantidad - detalle_oc.cantidad_recibida
            if cantidad_recibida > pendiente:
                return Response(
                    {'error': (f'Para {detalle_oc.producto.nombre}: '
                               f'pedido {detalle_oc.cantidad}, ya recibido '
                               f'{detalle_oc.cantidad_recibida}, pendiente {pendiente}')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Registrar el detalle de recepción
            DetalleRecepcion.objects.create(
                recepcion  = recepcion,
                detalle_oc = detalle_oc,
                cantidad   = cantidad_recibida,
            )

            # Actualizar cantidad recibida en el detalle de la OC
            detalle_oc.cantidad_recibida += cantidad_recibida
            detalle_oc.save(update_fields=['cantidad_recibida'])

            # ← Aumentar stock automáticamente via inventario/services.py
            aumentar_stock(
                producto    = detalle_oc.producto,
                cantidad    = cantidad_recibida,
                usuario     = request.user,
                origen_tipo = 'compra',
                origen_id   = recepcion.id,
                notas       = f'Recepción OC {orden.numero_oc}',
            )

            items_procesados.append(detalle_oc.producto.nombre)

        # Actualizar estado de la orden
        detalles    = orden.detalles.all()
        todo_completo = all(d.cantidad_recibida >= d.cantidad for d in detalles)
        orden.estado  = 'recibida' if todo_completo else 'parcial'
        orden.save(update_fields=['estado'])

        return Response({
            'recepcion':        RecepcionCompraSerializer(recepcion).data,
            'orden_estado':     orden.estado,
            'stock_actualizado': items_procesados,
        }, status=status.HTTP_201_CREATED)


class RecepcionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, orden_id):
        """Lista todas las recepciones de una orden de compra."""
        recepciones = RecepcionCompra.objects.filter(
            orden_id=orden_id
        ).select_related('recibido_por')
        return Response(RecepcionCompraSerializer(recepciones, many=True).data)