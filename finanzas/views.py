from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import CategoriaGasto, Gasto, CajaDiaria
from .serializers import (
    CategoriaGastoSerializer, GastoSerializer, CrearGastoSerializer,
    CajaDiariaSerializer, AbrirCajaSerializer, CerrarCajaSerializer,
)
from . import services


# ─── Categorías de gasto ──────────────────────────────────────────────────────

class CategoriaGastoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        categorias = CategoriaGasto.objects.all()
        return Response(CategoriaGastoSerializer(categorias, many=True).data)

    def post(self, request):
        serializer = CategoriaGastoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Gastos operativos ────────────────────────────────────────────────────────

class GastoListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Lista gastos. Filtros opcionales:
        ?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        ?categoria_id=3
        ?estado=pagado
        """
        qs = Gasto.objects.select_related('categoria', 'registrado_por')

        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin    = request.query_params.get('fecha_fin')
        categoria_id = request.query_params.get('categoria_id')
        estado       = request.query_params.get('estado')

        if fecha_inicio and fecha_fin:
            qs = qs.filter(fecha__range=(fecha_inicio, fecha_fin))
        if categoria_id:
            qs = qs.filter(categoria_id=categoria_id)
        if estado:
            qs = qs.filter(estado=estado)

        return Response(GastoSerializer(qs, many=True).data)

    def post(self, request):
        serializer = CrearGastoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            categoria = CategoriaGasto.objects.get(pk=data['categoria_id'])
        except CategoriaGasto.DoesNotExist:
            return Response({'error': 'Categoría no encontrada'},
                            status=status.HTTP_404_NOT_FOUND)

        gasto = Gasto.objects.create(
            categoria      = categoria,
            registrado_por = request.user,
            descripcion    = data['descripcion'],
            monto          = data['monto'],
            estado         = data['estado'],
            fecha          = data['fecha'],
            comprobante    = data.get('comprobante', ''),
            notas          = data.get('notas', ''),
        )

        return Response(GastoSerializer(gasto).data, status=status.HTTP_201_CREATED)


class GastoDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Gasto.objects.get(pk=pk), None
        except Gasto.DoesNotExist:
            return None, Response({'error': 'Gasto no encontrado'},
                                  status=status.HTTP_404_NOT_FOUND)

    def get(self, request, pk):
        gasto, err = self._get(pk)
        if err: return err
        return Response(GastoSerializer(gasto).data)

    def patch(self, request, pk):
        gasto, err = self._get(pk)
        if err: return err
        serializer = GastoSerializer(gasto, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        gasto, err = self._get(pk)
        if err: return err
        gasto.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Caja Diaria ──────────────────────────────────────────────────────────────

class AbrirCajaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Abre la caja del día para el usuario autenticado.
        Solo puede haber una caja abierta por cajero por día.
        """
        hoy = timezone.localdate()

        # Verificar si ya existe una caja abierta hoy
        if CajaDiaria.objects.filter(cajero=request.user, fecha=hoy).exists():
            return Response(
                {'error': 'Ya existe una caja para hoy. Ciérrala antes de abrir otra.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AbrirCajaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        caja = CajaDiaria.objects.create(
            cajero         = request.user,
            fecha          = hoy,
            monto_apertura = data['monto_apertura'],
            notas_apertura = data.get('notas_apertura', ''),
        )

        return Response(CajaDiariaSerializer(caja).data, status=status.HTTP_201_CREATED)


class CerrarCajaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """
        Cierra la caja, calcula el monto esperado y la diferencia.
        """
        try:
            caja = CajaDiaria.objects.get(pk=pk, cajero=request.user)
        except CajaDiaria.DoesNotExist:
            return Response({'error': 'Caja no encontrada'},
                            status=status.HTTP_404_NOT_FOUND)

        if caja.estado == 'cerrada':
            return Response({'error': 'Esta caja ya está cerrada'},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = CerrarCajaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Calcular monto esperado usando el servicio
        resumen        = services.resumen_caja(caja)
        monto_esperado = resumen['monto_esperado']
        monto_cierre   = data['monto_cierre']
        diferencia     = monto_cierre - monto_esperado

        caja.monto_cierre   = monto_cierre
        caja.monto_esperado = monto_esperado
        caja.diferencia     = diferencia
        caja.notas_cierre   = data.get('notas_cierre', '')
        caja.estado         = 'cerrada'
        caja.hora_cierre    = timezone.now()
        caja.save()

        return Response({
            'caja':            CajaDiariaSerializer(caja).data,
            'resumen_del_dia': resumen,
            'diferencia':      diferencia,
            'mensaje':         'Caja cerrada correctamente' if diferencia == 0
                               else f'Diferencia de S/ {diferencia}',
        })


class CajaListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Lista el historial de cajas del usuario. ?estado=abierta"""
        qs     = CajaDiaria.objects.filter(cajero=request.user)
        estado = request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return Response(CajaDiariaSerializer(qs, many=True).data)


class CajaActivaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Devuelve la caja abierta del día actual, si existe."""
        hoy = timezone.localdate()
        try:
            caja = CajaDiaria.objects.get(cajero=request.user, fecha=hoy, estado='abierta')
            return Response(CajaDiariaSerializer(caja).data)
        except CajaDiaria.DoesNotExist:
            return Response({'caja_abierta': False,
                             'mensaje': 'No hay caja abierta hoy'})


# ─── Reportes financieros ─────────────────────────────────────────────────────

class ReporteIngresosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /api/finanzas/reportes/ingresos/?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        """
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin    = request.query_params.get('fecha_fin')

        if not fecha_inicio or not fecha_fin:
            return Response({'error': 'Se requieren fecha_inicio y fecha_fin (YYYY-MM-DD)'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            reporte = services.reporte_ingresos(fecha_inicio, fecha_fin)
        except ValueError:
            return Response({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(reporte)


class ReporteEgresosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /api/finanzas/reportes/egresos/?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        """
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin    = request.query_params.get('fecha_fin')

        if not fecha_inicio or not fecha_fin:
            return Response({'error': 'Se requieren fecha_inicio y fecha_fin (YYYY-MM-DD)'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            reporte = services.reporte_egresos(fecha_inicio, fecha_fin)
        except ValueError:
            return Response({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(reporte)


class ReporteResumenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Resumen financiero completo del período.
        GET /api/finanzas/reportes/resumen/?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        """
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin    = request.query_params.get('fecha_fin')

        if not fecha_inicio or not fecha_fin:
            return Response({'error': 'Se requieren fecha_inicio y fecha_fin (YYYY-MM-DD)'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            reporte = services.reporte_resumen(fecha_inicio, fecha_fin)
        except ValueError:
            return Response({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(reporte)