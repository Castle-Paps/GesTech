import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogo.models import Producto
from inventario.services import descontar_stock, aumentar_stock
from ventas.models import Cliente

from .models import OrdenReparacion, PiezaUsada, ComprobanteReparacion
from .serializers import (
    OrdenReparacionSerializer,
    CrearOrdenReparacionSerializer,
    ActualizarOrdenSerializer,
    AgregarPiezaSerializer,
    ComprobanteReparacionSerializer,
    EmitirComprobanteSerializer,
    PiezaUsadaSerializer,
    siguiente_numero_comprobante,
)

Usuario = get_user_model()


# ── Utilidad interna ──────────────────────────────────────────────────────────

def _get_orden(pk):
    try:
        return OrdenReparacion.objects.select_related(
            'cliente', 'tecnico', 'recibido_por'
        ).prefetch_related('piezas__producto').get(pk=pk), None
    except OrdenReparacion.DoesNotExist:
        return None, Response(
            {'error': 'Orden de reparación no encontrada'},
            status=status.HTTP_404_NOT_FOUND,
        )


# ── Listado y creación ────────────────────────────────────────────────────────

class OrdenReparacionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista órdenes con filtros opcionales:
        ?estado=en_proceso|recibido|diagnostico|esperando|listo|entregado|sin_reparar
        ?prioridad=normal|urgente|express
        ?tecnico_id=3
        ?cliente_id=5
        ?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        """
        qs = OrdenReparacion.objects.select_related(
            'cliente', 'tecnico', 'recibido_por'
        ).prefetch_related('piezas__producto')

        estado       = request.query_params.get('estado')
        prioridad    = request.query_params.get('prioridad')
        tecnico_id   = request.query_params.get('tecnico_id')
        cliente_id   = request.query_params.get('cliente_id')
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin    = request.query_params.get('fecha_fin')

        if estado:
            qs = qs.filter(estado=estado)
        if prioridad:
            qs = qs.filter(prioridad=prioridad)
        if tecnico_id:
            qs = qs.filter(tecnico_id=tecnico_id)
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)
        if fecha_inicio and fecha_fin:
            qs = qs.filter(fecha_ingreso__date__range=(fecha_inicio, fecha_fin))

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
            cliente = Cliente.objects.get(pk=data['cliente'])
        except Cliente.DoesNotExist:
            return Response(
                {'error': 'Cliente no encontrado'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validar técnico (opcional)
        tecnico = None
        if data.get('tecnico_id'):
            try:
                tecnico = Usuario.objects.get(pk=data['tecnico_id'])
            except Usuario.DoesNotExist:
                return Response(
                    {'error': 'Técnico no encontrado'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        orden = OrdenReparacion.objects.create(
            numero_or         = f'OR-{uuid.uuid4().hex[:8].upper()}',
            cliente           = cliente,
            tecnico           = tecnico,
            recibido_por      = request.user,
            tipo_equipo       = data['tipo_equipo'],
            marca             = data.get('marca', ''),
            modelo            = data.get('modelo', ''),
            serie             = data.get('serie', ''),
            descripcion_falla = data['descripcion_falla'],
            accesorios        = data.get('accesorios', ''),
            observaciones     = data.get('observaciones', ''),
            prioridad         = data.get('prioridad', 'normal'),
            fecha_prometida   = data.get('fecha_prometida'),
            costo_mano_obra   = data.get('costo_mano_obra', 0),
        )

        return Response(
            OrdenReparacionSerializer(orden).data,
            status=status.HTTP_201_CREATED,
        )


# ── Detalle y actualización ───────────────────────────────────────────────────

class OrdenReparacionDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        orden, err = _get_orden(pk)
        if err: return err
        return Response(OrdenReparacionSerializer(orden).data)

    @transaction.atomic
    def patch(self, request, pk):
        """
        Actualiza diagnóstico, trabajo realizado, estado, mano de obra,
        técnico asignado o fecha prometida.
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado in ('entregado', 'sin_reparar'):
            return Response(
                {'error': f'No se puede modificar una orden en estado "{orden.estado}"'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ActualizarOrdenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        if 'estado' in data:
            nuevo_estado = data['estado']
            if nuevo_estado == 'entregado' and orden.estado != 'entregado':
                orden.fecha_entrega = timezone.now()
            orden.estado = nuevo_estado

        if 'tecnico_id' in data:
            if data['tecnico_id']:
                try:
                    orden.tecnico = Usuario.objects.get(pk=data['tecnico_id'])
                except Usuario.DoesNotExist:
                    return Response(
                        {'error': 'Técnico no encontrado'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                orden.tecnico = None

        for campo in ('diagnostico', 'trabajo_realizado', 'prioridad',
                      'fecha_prometida', 'observaciones'):
            if campo in data:
                setattr(orden, campo, data[campo])

        if 'costo_mano_obra' in data:
            orden.costo_mano_obra = data['costo_mano_obra']
            orden.total = orden.costo_mano_obra + orden.costo_piezas

        orden.save()
        return Response(OrdenReparacionSerializer(orden).data)


# ── Piezas usadas ─────────────────────────────────────────────────────────────

class PiezaUsadaView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        """
        Agrega una pieza a la reparación y descuenta el stock automáticamente.
        Body: { "producto_id": 5, "cantidad": 2, "precio_unitario": 45.00 }
        Si no se manda precio_unitario, se usa el precio_compra del producto.
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado in ('entregado', 'sin_reparar'):
            return Response(
                {'error': 'No se pueden agregar piezas a una orden cerrada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AgregarPiezaSerializer(data=request.data)
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

        precio_unitario = data.get('precio_unitario') or producto.precio_compra

        try:
            descontar_stock(
                producto    = producto,
                cantidad    = data['cantidad'],
                usuario     = request.user,
                origen_tipo = 'reparacion',   # corregido: era 'venta' por defecto
                origen_id   = orden.id,
                notas       = f'Pieza usada en OR {orden.numero_or}',
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        pieza = PiezaUsada.objects.create(
            orden           = orden,
            producto        = producto,
            cantidad        = data['cantidad'],
            precio_unitario = precio_unitario,
        )

        orden.recalcular_total()

        return Response(
            {
                'pieza': PiezaUsadaSerializer(pieza).data,
                'orden_total': str(orden.total),
            },
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def delete(self, request, pk, pieza_id):
        """Elimina una pieza y devuelve el stock al inventario."""
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado in ('entregado', 'sin_reparar'):
            return Response(
                {'error': 'No se pueden modificar piezas de una orden cerrada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            pieza = PiezaUsada.objects.select_related('producto').get(
                pk=pieza_id, orden=orden
            )
        except PiezaUsada.DoesNotExist:
            return Response(
                {'error': 'Pieza no encontrada en esta orden'},
                status=status.HTTP_404_NOT_FOUND,
            )

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

        return Response({'orden_total': str(orden.total)})


# ── Comprobante ───────────────────────────────────────────────────────────────

class ComprobanteReparacionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Consulta el comprobante de una orden."""
        orden, err = _get_orden(pk)
        if err: return err

        if not hasattr(orden, 'comprobante'):
            return Response(
                {'error': 'Esta orden aún no tiene comprobante'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ComprobanteReparacionSerializer(orden.comprobante).data)

    @transaction.atomic
    def post(self, request, pk):
        """
        Emite el comprobante de cobro de la reparación.
        Solo se puede emitir si la orden está en estado 'listo' o 'entregado'.
        Al emitir, la orden pasa automáticamente a 'entregado'.
        """
        orden, err = _get_orden(pk)
        if err: return err

        if orden.estado not in ('listo', 'entregado'):
            return Response(
                {'error': 'Solo se puede emitir comprobante cuando la reparación está lista o entregada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(orden, 'comprobante'):
            return Response(
                {'error': 'Esta orden ya tiene un comprobante emitido'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if orden.total <= 0:
            return Response(
                {'error': 'No se puede emitir comprobante con total $0. Revisa mano de obra y piezas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EmitirComprobanteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tipo      = serializer.validated_data['tipo_comprobante']
        serie_map = {'boleta': 'BR01', 'factura': 'FR01', 'ticket': 'TR01'}
        serie     = serie_map[tipo]
        numero    = siguiente_numero_comprobante(tipo, serie)

        comprobante = ComprobanteReparacion.objects.create(
            orden            = orden,
            tipo_comprobante = tipo,
            serie            = serie,
            numero           = numero,
            monto_total      = orden.total,
        )

        # Pasar a entregado si aún está en listo
        if orden.estado == 'listo':
            orden.estado       = 'entregado'
            orden.fecha_entrega = timezone.now()
            orden.save(update_fields=['estado', 'fecha_entrega'])

        return Response(
            ComprobanteReparacionSerializer(comprobante).data,
            status=status.HTTP_201_CREATED,
        )