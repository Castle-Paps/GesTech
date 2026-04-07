import uuid
from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogo.models import Producto
from inventario.services import aumentar_stock

from .models import Proveedor, OrdenCompra, DetalleOrdenCompra, RecepcionCompra, DetalleRecepcion
from .serializers import (
    ProveedorSerializer,
    OrdenCompraSerializer, CrearOrdenCompraSerializer, ActualizarOrdenSerializer,
    RecepcionCompraSerializer, CrearRecepcionSerializer,
)


# ── Utilidad interna ──────────────────────────────────────────────────────────

def _get_orden(pk):
    try:
        return OrdenCompra.objects.select_related(
            'proveedor', 'solicitado_por'
        ).prefetch_related('detalles__producto').get(pk=pk), None
    except OrdenCompra.DoesNotExist:
        return None, Response(
            {'error': 'Orden de compra no encontrada'},
            status=status.HTTP_404_NOT_FOUND,
        )


# ── Proveedores ───────────────────────────────────────────────────────────────

class ProveedorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista proveedores activos.
        Filtra con ?buscar=texto (nombre, ruc).
        Incluye inactivos con ?incluir_inactivos=true
        """
        qs = Proveedor.objects.all().order_by('nombre')

        incluir_inactivos = request.query_params.get('incluir_inactivos', '').lower() == 'true'
        if not incluir_inactivos:
            qs = qs.filter(activo=True)

        buscar = request.query_params.get('buscar')
        if buscar:
            qs = qs.filter(nombre__icontains=buscar) | qs.filter(ruc__icontains=buscar)

        return Response(ProveedorSerializer(qs, many=True).data)

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
            return None, Response(
                {'error': 'Proveedor no encontrado'}, status=status.HTTP_404_NOT_FOUND
            )

    def get(self, request, pk):
        proveedor, err = self._get(pk)
        if err: return err
        return Response(ProveedorSerializer(proveedor).data)

    def patch(self, request, pk):
        proveedor, err = self._get(pk)
        if err: return err
        serializer = ProveedorSerializer(proveedor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Borrado lógico: desactiva el proveedor."""
        proveedor, err = self._get(pk)
        if err: return err
        proveedor.activo = False
        proveedor.save(update_fields=['activo'])
        return Response({'mensaje': f'Proveedor "{proveedor.nombre}" desactivado'})


# ── Órdenes de Compra ─────────────────────────────────────────────────────────

class OrdenCompraListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista órdenes de compra con filtros opcionales:
        ?estado=borrador|enviada|recibida|parcial|anulada
        ?proveedor_id=3
        ?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        """
        qs = OrdenCompra.objects.select_related(
            'proveedor', 'solicitado_por'
        ).prefetch_related('detalles__producto')

        estado       = request.query_params.get('estado')
        proveedor_id = request.query_params.get('proveedor_id')
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin    = request.query_params.get('fecha_fin')

        if estado:
            qs = qs.filter(estado=estado)
        if proveedor_id:
            qs = qs.filter(proveedor_id=proveedor_id)
        if fecha_inicio and fecha_fin:
            qs = qs.filter(fecha_creacion__date__range=(fecha_inicio, fecha_fin))

        return Response(OrdenCompraSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        """Crea una OC con todos sus detalles en una sola llamada."""
        serializer = CrearOrdenCompraSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Validar proveedor
        try:
            proveedor = Proveedor.objects.get(pk=data['proveedor'], activo=True)
        except Proveedor.DoesNotExist:
            return Response(
                {'error': 'Proveedor no encontrado o inactivo'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validar productos y calcular totales
        items    = []
        subtotal = Decimal('0')

        for item in data['detalles']:
            try:
                producto = Producto.objects.get(pk=item['producto_id'], activo=True)
            except Producto.DoesNotExist:
                return Response(
                    {'error': f"Producto {item['producto_id']} no encontrado o inactivo"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            precio_unitario = item['precio_unitario']
            cantidad        = item['cantidad']
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

        orden = OrdenCompra.objects.create(
            numero_oc      = f'OC-{uuid.uuid4().hex[:8].upper()}',
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

    def get(self, request, pk):
        orden, err = _get_orden(pk)
        if err: return err
        return Response(OrdenCompraSerializer(orden).data)

    def patch(self, request, pk):
        """
        Cambia el estado manual de la orden (borrador → enviada) o edita las notas.
        Los estados 'recibida' y 'parcial' los asigna el sistema al recepcionar.
        Para anular usa DELETE.
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado in ('anulada', 'recibida'):
            return Response(
                {'error': f'No se puede modificar una orden en estado "{orden.estado}"'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ActualizarOrdenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        if 'estado' in data:
            # Solo se puede avanzar de borrador → enviada (no retroceder)
            FLUJO = {'borrador': ['enviada'], 'enviada': [], 'parcial': []}
            permitidos = FLUJO.get(orden.estado, [])
            if data['estado'] not in permitidos and data['estado'] != orden.estado:
                return Response(
                    {'error': f'Transición no permitida: {orden.estado} → {data["estado"]}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            orden.estado = data['estado']

        if 'notas' in data:
            orden.notas = data['notas']

        orden.save()
        return Response(OrdenCompraSerializer(orden).data)

    @transaction.atomic
    def delete(self, request, pk):
        """
        Anula la orden. Solo se puede anular si está en borrador o enviada
        (no si ya se recibió mercancía).
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado in ('recibida', 'parcial'):
            return Response(
                {'error': 'No se puede anular una orden que ya tiene recepciones de mercancía'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if orden.estado == 'anulada':
            return Response(
                {'error': 'Esta orden ya está anulada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        orden.estado = 'anulada'
        orden.save(update_fields=['estado'])
        return Response({'mensaje': f'Orden {orden.numero_oc} anulada correctamente'})


# ── Recepción de mercancía ────────────────────────────────────────────────────

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

        try:
            orden = OrdenCompra.objects.select_related('proveedor').get(pk=data['orden_id'])
        except OrdenCompra.DoesNotExist:
            return Response(
                {'error': 'Orden de compra no encontrada'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if orden.estado == 'anulada':
            return Response(
                {'error': 'No se puede recepcionar una orden anulada'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if orden.estado == 'recibida':
            return Response(
                {'error': 'Esta orden ya fue recibida completamente'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if orden.estado == 'borrador':
            return Response(
                {'error': 'La orden debe estar en estado "enviada" para recepcionar'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recepcion = RecepcionCompra.objects.create(
            orden        = orden,
            recibido_por = request.user,
            notas        = data.get('notas', ''),
        )

        items_procesados = []

        for item in data['items']:
            detalle_oc_id     = item['detalle_oc_id']
            cantidad_recibida = item['cantidad_recibida']

            try:
                detalle_oc = DetalleOrdenCompra.objects.select_related(
                    'producto'
                ).get(pk=detalle_oc_id, orden=orden)
            except DetalleOrdenCompra.DoesNotExist:
                return Response(
                    {'error': f'Detalle {detalle_oc_id} no pertenece a esta orden'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pendiente = detalle_oc.cantidad - detalle_oc.cantidad_recibida
            if cantidad_recibida > pendiente:
                return Response(
                    {
                        'error': (
                            f'Para "{detalle_oc.producto.nombre}": '
                            f'pedido {detalle_oc.cantidad}, '
                            f'ya recibido {detalle_oc.cantidad_recibida}, '
                            f'pendiente {pendiente}. '
                            f'No se pueden recibir {cantidad_recibida}.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            DetalleRecepcion.objects.create(
                recepcion  = recepcion,
                detalle_oc = detalle_oc,
                cantidad   = cantidad_recibida,
            )

            detalle_oc.cantidad_recibida += cantidad_recibida
            detalle_oc.save(update_fields=['cantidad_recibida'])

            aumentar_stock(
                producto    = detalle_oc.producto,
                cantidad    = cantidad_recibida,
                usuario     = request.user,
                origen_tipo = 'compra',
                origen_id   = recepcion.id,
                notas       = f'Recepción OC {orden.numero_oc}',
            )

            items_procesados.append({
                'producto': detalle_oc.producto.nombre,
                'cantidad': cantidad_recibida,
            })

        # Actualizar estado de la orden
        detalles      = orden.detalles.all()
        todo_completo = all(d.cantidad_recibida >= d.cantidad for d in detalles)
        orden.estado  = 'recibida' if todo_completo else 'parcial'
        orden.save(update_fields=['estado'])

        return Response({
            'recepcion':         RecepcionCompraSerializer(recepcion).data,
            'orden_estado':      orden.estado,
            'stock_actualizado': items_procesados,
        }, status=status.HTTP_201_CREATED)


class RecepcionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, orden_id):
        """Lista todas las recepciones de una orden de compra."""
        try:
            OrdenCompra.objects.get(pk=orden_id)
        except OrdenCompra.DoesNotExist:
            return Response(
                {'error': 'Orden de compra no encontrada'},
                status=status.HTTP_404_NOT_FOUND,
            )

        recepciones = RecepcionCompra.objects.filter(
            orden_id=orden_id
        ).select_related('recibido_por').prefetch_related('detalles__detalle_oc__producto')

        return Response(RecepcionCompraSerializer(recepciones, many=True).data)