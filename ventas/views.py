from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from decimal import Decimal
import uuid

from .models import Cliente, MetodoPago, Venta, DetalleVenta, Recibo
from .serializers import (ClienteSerializer, MetodoPagoSerializer,
                          VentaSerializer, CrearVentaSerializer, ReciboSerializer)
from catalogo.models import Producto


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
        # transaction.atomic garantiza que si algo falla, nada se guarda
        serializer = CrearVentaSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data     = serializer.validated_data
        detalles = data.get('detalles', [])

        if not detalles:
            return Response({'error': 'La venta debe tener al menos un producto'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Calcula el subtotal sumando cada línea de detalle
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

        descuento = Decimal(str(data.get('descuento', 0)))
        igv       = (subtotal - descuento) * Decimal('0.18')  # IGV 18%
        total     = subtotal - descuento + igv

        # Genera número de venta único
        numero_venta = f"V-{uuid.uuid4().hex[:8].upper()}"

        # Obtiene cliente y método de pago si vienen
        cliente_id     = data.get('cliente')
        metodo_pago_id = data.get('metodo_pago')

        cliente     = Cliente.objects.get(pk=cliente_id)     if cliente_id     else None
        metodo_pago = MetodoPago.objects.get(pk=metodo_pago_id) if metodo_pago_id else None

        # Crea la venta
        venta = Venta.objects.create(
            cliente      = cliente,
            vendedor     = request.user,  # el usuario autenticado es el vendedor
            metodo_pago  = metodo_pago,
            numero_venta = numero_venta,
            tipo_venta   = data.get('tipo_venta', 'directa'),
            subtotal     = subtotal,
            descuento    = descuento,
            igv          = igv,
            total        = total,
        )

        # Crea cada línea de detalle
        for item in items:
            DetalleVenta.objects.create(
                venta           = venta,
                producto        = item['producto'],
                cantidad        = item['cantidad'],
                precio_unitario = item['precio_unitario'],
                descuento_item  = item['descuento_item'],
                subtotal        = item['subtotal'],
            )

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
        # Genera el recibo de una venta existente
        try:
            venta = Venta.objects.get(pk=venta_id)
        except Venta.DoesNotExist:
            return Response({'error': 'Venta no encontrada'},
                            status=status.HTTP_404_NOT_FOUND)

        # Verifica que no tenga ya un recibo
        if hasattr(venta, 'recibo'):
            return Response({'error': 'Esta venta ya tiene un recibo'},
                            status=status.HTTP_400_BAD_REQUEST)

        tipo_comprobante = request.data.get('tipo_comprobante', 'ticket')
        cliente_nombre   = request.data.get('cliente_nombre', '')

        # Si tiene cliente registrado usa su nombre
        if venta.cliente and not cliente_nombre:
            cliente_nombre = venta.cliente.nombre

        # Serie y número automático simple
        serie  = 'B001' if tipo_comprobante == 'boleta' else 'F001' if tipo_comprobante == 'factura' else 'T001'
        ultimo = Recibo.objects.filter(tipo_comprobante=tipo_comprobante, serie=serie).count()
        numero = str(ultimo + 1).zfill(8)  # ej: 00000001

        recibo = Recibo.objects.create(
            venta            = venta,
            tipo_comprobante = tipo_comprobante,
            serie            = serie,
            numero           = numero,
            cliente_nombre   = cliente_nombre,
            monto_total      = venta.total,
        )

        return Response(ReciboSerializer(recibo).data, status=status.HTTP_201_CREATED)