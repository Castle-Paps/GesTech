from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from decimal import Decimal
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .services_mp import crear_preferencia


from .models import Cliente, MetodoPago, Venta, DetalleVenta, Recibo
from .serializers import (ClienteSerializer, MetodoPagoSerializer,
                          VentaSerializer, CrearVentaSerializer, ReciboSerializer)
from catalogo.models import Producto
from inventario.services import descontar_stock  # ← importa el servicio


class ClienteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        clientes   = Cliente.objects.all()
        serializer = ClienteSerializer(clientes, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ClienteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MetodoPagoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        metodos    = MetodoPago.objects.filter(activo=True)
        serializer = MetodoPagoSerializer(metodos, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MetodoPagoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CrearVentaView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CrearVentaSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data     = serializer.validated_data
        detalles = data.get('detalles', [])

        if not detalles:
            return Response({'error': 'La venta debe tener al menos un producto'},
                            status=status.HTTP_400_BAD_REQUEST)

        subtotal = Decimal(0)
        items    = []

        for item in detalles:
            try:
                producto = Producto.objects.get(pk=item['producto_id'])
            except Producto.DoesNotExist:
                return Response({'error': f"Producto {item['producto_id']} no encontrado"},
                                status=status.HTTP_404_NOT_FOUND)

            cantidad        = int(item['cantidad'])
            precio_unitario = Decimal(str(item.get('precio_unitario', producto.precio_venta)))
            descuento_item  = Decimal(str(item.get('descuento_item', 0)))
            subtotal_item   = (precio_unitario * cantidad) - descuento_item

            subtotal += subtotal_item
            items.append({
                'producto':        producto,
                'cantidad':        cantidad,
                'precio_unitario': precio_unitario,
                'descuento_item':  descuento_item,
                'subtotal':        subtotal_item,
            })

        descuento    = Decimal(str(data.get('descuento', 0)))
        igv          = (subtotal - descuento) * Decimal('0.18')
        total        = subtotal - descuento + igv
        numero_venta = f"V-{uuid.uuid4().hex[:8].upper()}"

        cliente_id     = data.get('cliente')
        metodo_pago_id = data.get('metodo_pago')

        cliente     = Cliente.objects.get(pk=cliente_id)        if cliente_id     else None
        metodo_pago = MetodoPago.objects.get(pk=metodo_pago_id) if metodo_pago_id else None

        venta = Venta.objects.create(
            cliente      = cliente,
            vendedor     = request.user,
            metodo_pago  = metodo_pago,
            numero_venta = numero_venta,
            tipo_venta   = data.get('tipo_venta', 'directa'),
            subtotal     = subtotal,
            descuento    = descuento,
            igv          = igv,
            total        = total,
        )

        for item in items:
            DetalleVenta.objects.create(
                venta           = venta,
                producto        = item['producto'],
                cantidad        = item['cantidad'],
                precio_unitario = item['precio_unitario'],
                descuento_item  = item['descuento_item'],
                subtotal        = item['subtotal'],
            )

            # ← descuenta el stock automáticamente después de crear el detalle
            try:
                descontar_stock(
                    producto   = item['producto'],
                    cantidad   = item['cantidad'],
                    usuario    = request.user,
                    origen_id  = venta.id,
                )
            except ValueError as e:
                # Si no hay stock suficiente cancela toda la venta
                raise transaction.atomic.Rollback(str(e))

        return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)


class VentaListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ventas     = Venta.objects.all().order_by('-fecha_venta')
        serializer = VentaSerializer(ventas, many=True)
        return Response(serializer.data)


class VentaDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            venta      = Venta.objects.get(pk=pk)
            serializer = VentaSerializer(venta)
            return Response(serializer.data)
        except Venta.DoesNotExist:
            return Response({'error': 'Venta no encontrada'},
                            status=status.HTTP_404_NOT_FOUND)


class ReciboView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, venta_id):
        try:
            venta = Venta.objects.get(pk=venta_id)
        except Venta.DoesNotExist:
            return Response({'error': 'Venta no encontrada'},
                            status=status.HTTP_404_NOT_FOUND)

        if hasattr(venta, 'recibo'):
            return Response({'error': 'Esta venta ya tiene un recibo'},
                            status=status.HTTP_400_BAD_REQUEST)

        tipo_comprobante = request.data.get('tipo_comprobante', 'ticket')
        cliente_nombre   = request.data.get('cliente_nombre', '')

        if venta.cliente and not cliente_nombre:
            cliente_nombre = venta.cliente.nombre

        serie  = 'B001' if tipo_comprobante == 'boleta' else 'F001' if tipo_comprobante == 'factura' else 'T001'
        ultimo = Recibo.objects.filter(tipo_comprobante=tipo_comprobante, serie=serie).count()
        numero = str(ultimo + 1).zfill(8)

        recibo = Recibo.objects.create(
            venta            = venta,
            tipo_comprobante = tipo_comprobante,
            serie            = serie,
            numero           = numero,
            cliente_nombre   = cliente_nombre,
            monto_total      = venta.total,
        )

        return Response(ReciboSerializer(recibo).data, status=status.HTTP_201_CREATED)
    




class CrearPagoMPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, venta_id):
        try:
            venta = Venta.objects.get(pk=venta_id)
        except Venta.DoesNotExist:
            return Response({'error': 'Venta no encontrada'},
                            status=status.HTTP_404_NOT_FOUND)

        if venta.estado == 'completada':
            return Response({'error': 'Esta venta ya fue pagada'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            preferencia = crear_preferencia(venta)
            venta.mp_preference_id = preferencia['id']
            venta.save()

            return Response({
                'preference_id':      preferencia['id'],
                'init_point':         preferencia['init_point'],
                'sandbox_init_point': preferencia['sandbox_init_point'],
            })
        except Exception as e:
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class WebhookMPView(APIView):
    permission_classes     = []
    authentication_classes = []

    def post(self, request):
        data = request.data

        if data.get('type') == 'payment':
            payment_id = data.get('data', {}).get('id')
            if not payment_id:
                return Response(status=200)

            try:
                import mercadopago
                from django.conf import settings
                sdk  = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
                pago = sdk.payment().get(payment_id)['response']

                numero_venta = pago.get('external_reference')
                mp_status    = pago.get('status')

                venta = Venta.objects.get(numero_venta=numero_venta)
                venta.mp_payment_id = str(payment_id)
                venta.mp_status     = mp_status

                if mp_status == 'approved':
                    venta.estado = 'completada'
                    venta.save()

                    if not hasattr(venta, 'recibo'):
                        cliente_nombre = venta.cliente.nombre if venta.cliente else 'Cliente General'
                        ultimo = Recibo.objects.filter(tipo_comprobante='ticket', serie='T001').count()
                        numero = str(ultimo + 1).zfill(8)
                        Recibo.objects.create(
                            venta            = venta,
                            tipo_comprobante = 'ticket',
                            serie            = 'T001',
                            numero           = numero,
                            cliente_nombre   = cliente_nombre,
                            monto_total      = venta.total,
                        )
                elif mp_status in ('rejected', 'cancelled'):
                    venta.estado = 'anulada'
                    venta.save()
                else:
                    venta.save()

            except Exception as e:
                print(f"Error webhook: {e}")

        return Response(status=200)