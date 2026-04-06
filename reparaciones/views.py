import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import OrdenReparacion, PiezaUsada, ComprobanteReparacion
from .serializers import (
    OrdenReparacionSerializer, CrearOrdenReparacionSerializer,
    ActualizarOrdenSerializer, AgregarPiezaSerializer,
    ComprobanteReparacionSerializer, EmitirComprobanteSerializer,
)
from ventas.models import Cliente
from catalogo.models import Producto
from inventario.services import descontar_stock
from django.conf import settings
from django.contrib.auth import get_user_model

Usuario = get_user_model()


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_orden(pk):
    try:
        return OrdenReparacion.objects.get(pk=pk), None
    except OrdenReparacion.DoesNotExist:
        return None, Response({'error': 'Orden de reparación no encontrada'},
                              status=status.HTTP_404_NOT_FOUND)


# ─── Listado y creación de órdenes ───────────────────────────────────────────

class OrdenReparacionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista todas las órdenes. Filtra por estado con ?estado=en_proceso
        """
        qs = OrdenReparacion.objects.select_related(
            'cliente', 'tecnico', 'recibido_por'
        )
        estado = request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)

        tecnico_id = request.query_params.get('tecnico_id')
        if tecnico_id:
            qs = qs.filter(tecnico_id=tecnico_id)

        return Response(OrdenReparacionSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        """Abre una nueva orden al recibir el equipo del cliente."""
        serializer = CrearOrdenReparacionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Validar cliente
        try:
            cliente = Cliente.objects.get(pk=data['cliente_id'])
        except Cliente.DoesNotExist:
            return Response({'error': 'Cliente no encontrado'},
                            status=status.HTTP_404_NOT_FOUND)

        # Validar técnico (opcional)
        tecnico = None
        if data.get('tecnico_id'):
            try:
                tecnico = Usuario.objects.get(pk=data['tecnico_id'])
            except Usuario.DoesNotExist:
                return Response({'error': 'Técnico no encontrado'},
                                status=status.HTTP_404_NOT_FOUND)

        numero_or = f"OR-{uuid.uuid4().hex[:8].upper()}"

        orden = OrdenReparacion.objects.create(
            numero_or        = numero_or,
            cliente          = cliente,
            tecnico          = tecnico,
            recibido_por     = request.user,
            tipo_equipo      = data['tipo_equipo'],
            marca            = data.get('marca', ''),
            modelo           = data.get('modelo', ''),
            serie            = data.get('serie', ''),
            descripcion_falla = data['descripcion_falla'],
            accesorios       = data.get('accesorios', ''),
            observaciones    = data.get('observaciones', ''),
            prioridad        = data.get('prioridad', 'normal'),
            fecha_prometida  = data.get('fecha_prometida'),
        )

        return Response(OrdenReparacionSerializer(orden).data,
                        status=status.HTTP_201_CREATED)


# ─── Detalle y actualización de una orden ────────────────────────────────────

class OrdenReparacionDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        orden, err = _get_orden(pk)
        if err: return err
        return Response(OrdenReparacionSerializer(orden).data)

    @transaction.atomic
    def patch(self, request, pk):
        """
        El técnico actualiza diagnóstico, trabajo realizado, estado y mano de obra.
        También permite reasignar técnico o cambiar fecha prometida.
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado == 'entregado':
            return Response({'error': 'No se puede modificar una orden ya entregada'},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = ActualizarOrdenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        if 'estado' in data:
            nuevo_estado = data['estado']

            # Al marcar como entregado, registrar la fecha real
            if nuevo_estado == 'entregado' and orden.estado != 'entregado':
                orden.fecha_entrega = timezone.now()

            orden.estado = nuevo_estado

        if 'diagnostico' in data:
            orden.diagnostico = data['diagnostico']

        if 'trabajo_realizado' in data:
            orden.trabajo_realizado = data['trabajo_realizado']

        if 'costo_mano_obra' in data:
            orden.costo_mano_obra = data['costo_mano_obra']
            # Recalcular total
            orden.total = orden.costo_mano_obra + orden.costo_piezas

        if 'tecnico_id' in data:
            if data['tecnico_id']:
                try:
                    orden.tecnico = Usuario.objects.get(pk=data['tecnico_id'])
                except Usuario.DoesNotExist:
                    return Response({'error': 'Técnico no encontrado'},
                                    status=status.HTTP_404_NOT_FOUND)
            else:
                orden.tecnico = None

        if 'fecha_prometida' in data:
            orden.fecha_prometida = data['fecha_prometida']

        orden.save()
        return Response(OrdenReparacionSerializer(orden).data)


# ─── Piezas usadas en la reparación ──────────────────────────────────────────

class PiezaUsadaView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        """
        Agrega una pieza a la reparación y descuenta el stock automáticamente.

        Body: { "producto_id": 5, "cantidad": 2, "precio_unitario": 45.00 }
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado in ('entregado', 'sin_reparar'):
            return Response(
                {'error': 'No se pueden agregar piezas a una orden cerrada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AgregarPiezaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            producto = Producto.objects.get(pk=data['producto_id'], activo=True)
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'},
                            status=status.HTTP_404_NOT_FOUND)

        # Si no se especifica precio, usar el precio de compra del producto
        precio_unitario = data.get('precio_unitario') or producto.precio_compra

        # Descontar stock — lanza ValueError si no hay suficiente
        try:
            descontar_stock(
                producto  = producto,
                cantidad  = data['cantidad'],
                usuario   = request.user,
                origen_id = orden.id,
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        pieza = PiezaUsada.objects.create(
            orden           = orden,
            producto        = producto,
            cantidad        = data['cantidad'],
            precio_unitario = precio_unitario,
        )

        # Recalcular costo_piezas y total de la orden
        orden.recalcular_total()

        return Response({
            'pieza':       {'id': pieza.id, 'producto': producto.nombre,
                            'cantidad': pieza.cantidad,
                            'precio_unitario': str(pieza.precio_unitario)},
            'orden_total': str(orden.total),
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, pieza_id):
        """
        Elimina una pieza de la orden y DEVUELVE el stock al inventario.
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado in ('entregado', 'sin_reparar'):
            return Response(
                {'error': 'No se pueden modificar piezas de una orden cerrada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            pieza = PiezaUsada.objects.get(pk=pieza_id, orden=orden)
        except PiezaUsada.DoesNotExist:
            return Response({'error': 'Pieza no encontrada en esta orden'},
                            status=status.HTTP_404_NOT_FOUND)

        # Devolver el stock
        from inventario.services import aumentar_stock
        aumentar_stock(
            producto    = pieza.producto,
            cantidad    = pieza.cantidad,
            usuario     = request.user,
            origen_tipo = 'ajuste_manual',
            origen_id   = orden.id,
            notas       = f'Pieza retirada de OR {orden.numero_or}',
        )

        pieza.delete()
        orden.recalcular_total()

        return Response({'orden_total': str(orden.total)},
                        status=status.HTTP_200_OK)


# ─── Comprobante de la reparación ─────────────────────────────────────────────

class ComprobanteReparacionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """
        Emite el comprobante de cobro de la reparación.
        Solo se puede emitir si la orden está en estado 'listo' o 'entregado'.
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado not in ('listo', 'entregado'):
            return Response(
                {'error': 'Solo se puede emitir comprobante cuando la reparación está lista o entregada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if hasattr(orden, 'comprobante'):
            return Response({'error': 'Esta orden ya tiene un comprobante emitido'},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = EmitirComprobanteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tipo = serializer.validated_data['tipo_comprobante']

        # Generar serie y número correlativo
        serie_map = {'boleta': 'BR01', 'factura': 'FR01', 'ticket': 'TR01'}
        serie     = serie_map[tipo]
        ultimo    = ComprobanteReparacion.objects.filter(
            tipo_comprobante=tipo, serie=serie
        ).count()
        numero = str(ultimo + 1).zfill(8)

        comprobante = ComprobanteReparacion.objects.create(
            orden            = orden,
            tipo_comprobante = tipo,
            serie            = serie,
            numero           = numero,
            monto_total      = orden.total,
        )

        # Marcar la orden como entregada si aún no lo está
        if orden.estado == 'listo':
            orden.estado       = 'entregado'
            orden.fecha_entrega = timezone.now()
            orden.save(update_fields=['estado', 'fecha_entrega'])

        return Response(ComprobanteReparacionSerializer(comprobante).data,
                        status=status.HTTP_201_CREATED)

    def get(self, request, pk):
        """Consulta el comprobante de una orden."""
        orden, err = _get_orden(pk)
        if err: return err

        if not hasattr(orden, 'comprobante'):
            return Response({'error': 'Esta orden no tiene comprobante aún'},
                            status=status.HTTP_404_NOT_FOUND)

        return Response(ComprobanteReparacionSerializer(orden.comprobante).data)