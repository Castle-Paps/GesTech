"""
finanzas/services.py
Consolida datos de ventas, reparaciones y compras para los reportes.
"""
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
import datetime


def _rango_fechas(fecha_inicio, fecha_fin):
    """Convierte strings a datetime con zona horaria."""
    if isinstance(fecha_inicio, str):
        fecha_inicio = datetime.date.fromisoformat(fecha_inicio)
    if isinstance(fecha_fin, str):
        fecha_fin = datetime.date.fromisoformat(fecha_fin)
    inicio = timezone.make_aware(datetime.datetime.combine(fecha_inicio, datetime.time.min))
    fin    = timezone.make_aware(datetime.datetime.combine(fecha_fin,    datetime.time.max))
    return inicio, fin


def reporte_ingresos(fecha_inicio, fecha_fin) -> dict:
    """
    Consolida ingresos de ventas y reparaciones en el período.
    """
    from ventas.models import Venta
    from reparaciones.models import ComprobanteReparacion

    inicio, fin = _rango_fechas(fecha_inicio, fecha_fin)

    # Ingresos por ventas (no anuladas)
    ventas = Venta.objects.filter(
        fecha_venta__range=(inicio, fin),
        estado='completada'
    ).aggregate(
        total      = Sum('total'),
        cantidad   = Count('id'),
        subtotal   = Sum('subtotal'),
        igv        = Sum('igv'),
        descuentos = Sum('descuento'),
    )

    # Ingresos por reparaciones (comprobantes emitidos, no anulados)
    reparaciones = ComprobanteReparacion.objects.filter(
        fecha_emision__range=(inicio, fin),
        estado='emitido'
    ).aggregate(
        total    = Sum('monto_total'),
        cantidad = Count('id'),
    )

    total_ventas       = ventas['total']       or Decimal('0')
    total_reparaciones = reparaciones['total'] or Decimal('0')

    return {
        'periodo': {'inicio': str(fecha_inicio), 'fin': str(fecha_fin)},
        'ventas': {
            'total':      total_ventas,
            'cantidad':   ventas['cantidad']   or 0,
            'subtotal':   ventas['subtotal']   or Decimal('0'),
            'igv':        ventas['igv']        or Decimal('0'),
            'descuentos': ventas['descuentos'] or Decimal('0'),
        },
        'reparaciones': {
            'total':    total_reparaciones,
            'cantidad': reparaciones['cantidad'] or 0,
        },
        'total_ingresos': total_ventas + total_reparaciones,
    }


def reporte_egresos(fecha_inicio, fecha_fin) -> dict:
    """
    Consolida egresos: compras recibidas + gastos operativos en el período.
    """
    from compras.models import OrdenCompra
    from .models import Gasto

    inicio, fin = _rango_fechas(fecha_inicio, fecha_fin)

    # Egresos por compras (órdenes recibidas o parcialmente recibidas)
    compras = OrdenCompra.objects.filter(
        fecha_creacion__range=(inicio, fin),
        estado__in=['recibida', 'parcial']
    ).aggregate(
        total    = Sum('total'),
        cantidad = Count('id'),
    )

    # Gastos operativos pagados en el período
    gastos = Gasto.objects.filter(
        fecha__range=(fecha_inicio, fecha_fin),
        estado='pagado'
    ).aggregate(
        total    = Sum('monto'),
        cantidad = Count('id'),
    )

    # Gastos agrupados por categoría
    gastos_por_categoria = list(
        Gasto.objects.filter(
            fecha__range=(fecha_inicio, fecha_fin),
            estado='pagado'
        ).values('categoria__nombre')
         .annotate(total=Sum('monto'), cantidad=Count('id'))
         .order_by('-total')
    )

    total_compras = compras['total'] or Decimal('0')
    total_gastos  = gastos['total']  or Decimal('0')

    return {
        'periodo': {'inicio': str(fecha_inicio), 'fin': str(fecha_fin)},
        'compras': {
            'total':    total_compras,
            'cantidad': compras['cantidad'] or 0,
        },
        'gastos_operativos': {
            'total':              total_gastos,
            'cantidad':           gastos['cantidad'] or 0,
            'por_categoria':      gastos_por_categoria,
        },
        'total_egresos': total_compras + total_gastos,
    }


def reporte_resumen(fecha_inicio, fecha_fin) -> dict:
    """
    Resumen financiero completo del período: ingresos, egresos y utilidad bruta.
    """
    ingresos = reporte_ingresos(fecha_inicio, fecha_fin)
    egresos  = reporte_egresos(fecha_inicio, fecha_fin)

    total_ingresos = ingresos['total_ingresos']
    total_egresos  = egresos['total_egresos']
    utilidad       = total_ingresos - total_egresos

    return {
        'periodo':          ingresos['periodo'],
        'total_ingresos':   total_ingresos,
        'total_egresos':    total_egresos,
        'utilidad_bruta':   utilidad,
        'rentable':         utilidad > 0,
        'detalle_ingresos': ingresos,
        'detalle_egresos':  egresos,
    }


def resumen_caja(caja) -> dict:
    """
    Calcula el monto esperado en caja al cierre:
    apertura + ingresos del día (ventas + reparaciones) - gastos pagados en caja.
    """
    from ventas.models import Venta
    from reparaciones.models import ComprobanteReparacion

    fecha  = caja.fecha
    inicio, fin = _rango_fechas(fecha, fecha)

    ventas = Venta.objects.filter(
        fecha_venta__range=(inicio, fin),
        estado='completada'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')

    reparaciones = ComprobanteReparacion.objects.filter(
        fecha_emision__range=(inicio, fin),
        estado='emitido'
    ).aggregate(total=Sum('monto_total'))['total'] or Decimal('0')

    monto_esperado = caja.monto_apertura + ventas + reparaciones

    return {
        'monto_apertura':   caja.monto_apertura,
        'ingresos_ventas':  ventas,
        'ingresos_reparaciones': reparaciones,
        'monto_esperado':   monto_esperado,
    }