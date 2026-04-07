from decimal import Decimal

import uuid
from django.db import transaction
from django.db.models import Max
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogo.models import Producto
from inventario.services import descontar_stock, aumentar_stock

from .models import Cliente, MetodoPago, Venta, DetalleVenta, Recibo
from .serializers import (
    ClienteSerializer, MetodoPagoSerializer,
    VentaSerializer, CrearVentaSerializer,
    ReciboSerializer, AnularVentaSerializer,
)
from .services_mp import crear_preferencia


# ── Utilidades internas ───────────────────────────────────────────────────────

def _siguiente_numero_recibo(tipo_comprobante: str, serie: str) -> str:
    """
    Genera el siguiente número correlativo de forma segura usando
    select_for_update para evitar duplicados en concurrencia.
    """
    ultimo = (
        Recibo.objects
        .select_for_update()
        .filter(tipo_comprobante=tipo_comprobante, serie=serie)
        .aggregate(max_num=Max('numero'))['max_num']
    )
    siguiente = (int(ultimo) + 1) if ultimo else 1
    return str(siguiente).zfill(8)


def _get_venta(pk):
    try:
        return Venta.objects.get(pk=pk), None
    except Venta.DoesNotExist:
        return None, Response(
            {'error': 'Venta no encontrada'}, status=status.HTTP_404_NOT_FOUND
        )


# ── Clientes ──────────────────────────────────────────────────────────────────

class ClienteListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Lista clientes. Filtra con ?buscar=texto (nombre, dni_ruc, email)."""
        qs     = Cliente.objects.all().order_by('nombre')
        buscar = request.query_params.get('buscar')
        if buscar:
            qs = qs.filter(nombre__icontains=buscar) \
                 | qs.filter(dni_ruc__icontains=buscar) \
                 | qs.filter(email__icontains=buscar)
        return Response(ClienteSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ClienteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClienteDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Cliente.objects.get(pk=pk), None
        except Cliente.DoesNotExist:
            return None, Response(
                {'error': 'Cliente no encontrado'}, status=status.HTTP_404_NOT_FOUND
            )

    def get(self, request, pk):
        cliente, err = self._get(pk)
        if err: return err
        return Response(ClienteSerializer(cliente).data)

    def patch(self, request, pk):
        cliente, err = self._get(pk)
        if err: return err
        serializer = ClienteSerializer(cliente, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Métodos de pago ───────────────────────────────────────────────────────────

class MetodoPagoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        metodos = MetodoPago.objects.filter(activo=True)
        return Response(MetodoPagoSerializer(metodos, many=True).data)

    def post(self, request):
        serializer = MetodoPagoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Ventas ────────────────────────────────────────────────────────────────────

class VentaListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista ventas con filtros opcionales:
        ?estado=completada
        ?tipo_venta=directa
        ?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        ?cliente_id=5
        """
        qs = Venta.objects.select_related(
            'cliente', 'vendedor', 'metodo_pago'
        ).prefetch_related('detalles__producto').order_by('-fecha_venta')

        estado       = request.query_params.get('estado')
        tipo_venta   = request.query_params.get('tipo_venta')
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin    = request.query_params.get('fecha_fin')
        cliente_id   = request.query_params.get('cliente_id')

        if estado:
            qs = qs.filter(estado=estado)
        if tipo_venta:
            qs = qs.filter(tipo_venta=tipo_venta)
        if fecha_inicio and fecha_fin:
            qs = qs.filter(fecha_venta__date__range=(fecha_inicio, fecha_fin))
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)

        return Response(VentaSerializer(qs, many=True).data)


class CrearVentaView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CrearVentaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # ── Resolver cliente y método de pago ─────────────────────────────────
        cliente, metodo_pago = None, None

        if data.get('cliente'):
            try:
                cliente = Cliente.objects.get(pk=data['cliente'])
            except Cliente.DoesNotExist:
                return Response(
                    {'error': 'Cliente no encontrado'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if data.get('metodo_pago'):
            try:
                metodo_pago = MetodoPago.objects.get(pk=data['metodo_pago'], activo=True)
            except MetodoPago.DoesNotExist:
                return Response(
                    {'error': 'Método de pago no encontrado o inactivo'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # ── Validar productos y calcular totales ──────────────────────────────
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

            cantidad        = item['cantidad']
            precio_unitario = item.get('precio_unitario') or producto.precio_venta
            descuento_item  = item.get('descuento_item', Decimal('0'))
            subtotal_item   = (precio_unitario * cantidad) - descuento_item

            items.append({
                'producto':        producto,
                'cantidad':        cantidad,
                'precio_unitario': precio_unitario,
                'descuento_item':  descuento_item,
                'subtotal':        subtotal_item,
                'agrupacion':      item.get('agrupacion', ''),
            })
            subtotal += subtotal_item

        descuento = data.get('descuento', Decimal('0'))
        igv       = (subtotal - descuento) * Decimal('0.18')
        total     = subtotal - descuento + igv

        # ── Crear la venta ────────────────────────────────────────────────────
        venta = Venta.objects.create(
            cliente      = cliente,
            vendedor     = request.user,
            metodo_pago  = metodo_pago,
            numero_venta = f'V-{uuid.uuid4().hex[:8].upper()}',
            tipo_venta   = data.get('tipo_venta', 'directa'),
            subtotal     = subtotal,
            descuento    = descuento,
            igv          = igv,
            total        = total,
        )

        # ── Crear detalles y descontar stock ──────────────────────────────────
        for item in items:
            DetalleVenta.objects.create(
                venta           = venta,
                producto        = item['producto'],
                cantidad        = item['cantidad'],
                precio_unitario = item['precio_unitario'],
                descuento_item  = item['descuento_item'],
                subtotal        = item['subtotal'],
                agrupacion      = item['agrupacion'],
            )
            try:
                descontar_stock(
                    producto    = item['producto'],
                    cantidad    = item['cantidad'],
                    usuario     = request.user,
                    origen_tipo = 'venta',
                    origen_id   = venta.id,
                )
            except ValueError as e:
                # Lanza excepción para que @transaction.atomic haga rollback
                raise ValueError(str(e))

        return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)


class VentaDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        venta, err = _get_venta(pk)
        if err: return err
        return Response(VentaSerializer(venta).data)

    @transaction.atomic
    def patch(self, request, pk):
        """
        Anula una venta y devuelve el stock de todos sus productos.
        PATCH /api/ventas/<pk>/  con { "estado": "anulada", "motivo": "..." }
        """
        venta, err = _get_venta(pk)
        if err: return err

        serializer = AnularVentaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if venta.estado == 'anulada':
            return Response(
                {'error': 'Esta venta ya está anulada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Devolver stock de cada detalle
        for detalle in venta.detalles.select_related('producto').all():
            aumentar_stock(
                producto    = detalle.producto,
                cantidad    = detalle.cantidad,
                usuario     = request.user,
                origen_tipo = 'ajuste_manual',
                origen_id   = venta.id,
                notas       = f'Anulación venta {venta.numero_venta}',
            )

        venta.estado = 'anulada'
        venta.save(update_fields=['estado'])

        # Anular el recibo si existe
        if hasattr(venta, 'recibo') and venta.recibo.estado == 'emitido':
            venta.recibo.estado = 'anulado'
            venta.recibo.save(update_fields=['estado'])

        return Response(VentaSerializer(venta).data)


# ── Recibos ───────────────────────────────────────────────────────────────────

class ReciboView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, venta_id):
        venta, err = _get_venta(venta_id)
        if err: return err

        if venta.estado == 'anulada':
            return Response(
                {'error': 'No se puede emitir recibo para una venta anulada'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if hasattr(venta, 'recibo'):
            return Response(
                {'error': 'Esta venta ya tiene un recibo'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tipo_comprobante = request.data.get('tipo_comprobante', 'ticket')
        if tipo_comprobante not in ('boleta', 'factura', 'ticket'):
            return Response(
                {'error': 'tipo_comprobante debe ser boleta, factura o ticket'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente_nombre = request.data.get('cliente_nombre', '')
        if venta.cliente and not cliente_nombre:
            cliente_nombre = venta.cliente.nombre

        serie_map = {'boleta': 'B001', 'factura': 'F001', 'ticket': 'T001'}
        serie     = serie_map[tipo_comprobante]
        numero    = _siguiente_numero_recibo(tipo_comprobante, serie)

        recibo = Recibo.objects.create(
            venta            = venta,
            tipo_comprobante = tipo_comprobante,
            serie            = serie,
            numero           = numero,
            cliente_nombre   = cliente_nombre,
            monto_total      = venta.total,
        )

        # Marcar la venta como completada al emitir recibo
        if venta.estado == 'pendiente':
            venta.estado = 'completada'
            venta.save(update_fields=['estado'])

        return Response(ReciboSerializer(recibo).data, status=status.HTTP_201_CREATED)

    def get(self, request, venta_id):
        venta, err = _get_venta(venta_id)
        if err: return err
        if not hasattr(venta, 'recibo'):
            return Response(
                {'error': 'Esta venta no tiene recibo aún'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ReciboSerializer(venta.recibo).data)


# ── Mercado Pago ──────────────────────────────────────────────────────────────

class CrearPagoMPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, venta_id):
        venta, err = _get_venta(venta_id)
        if err: return err

        if venta.estado == 'completada':
            return Response(
                {'error': 'Esta venta ya fue pagada'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if venta.estado == 'anulada':
            return Response(
                {'error': 'No se puede pagar una venta anulada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            preferencia            = crear_preferencia(venta)
            venta.mp_preference_id = preferencia['id']
            venta.save(update_fields=['mp_preference_id'])
            return Response({
                'preference_id':      preferencia['id'],
                'init_point':         preferencia['init_point'],
                'sandbox_init_point': preferencia.get('sandbox_init_point'),
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class WebhookMPView(APIView):
    """
    Webhook de Mercado Pago. La lógica completa de validación de firma
    y procesamiento vive en pagos/views.py (WebhookView).
    Este endpoint solo existe como alias por compatibilidad.
    """
    permission_classes     = []
    authentication_classes = []

    def post(self, request):
        from pagos.views import WebhookView
        return WebhookView.as_view()(request._request)