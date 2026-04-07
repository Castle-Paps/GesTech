import mercadopago
from django.conf import settings


def _get_sdk():
    return mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)


def crear_preferencia(venta):
    """
    Crea una preferencia de pago en Mercado Pago para una venta.
    La URL base del webhook se lee desde settings.SITE_URL para no
    hardcodear URLs de desarrollo.
    """
    sdk  = _get_sdk()
    base = getattr(settings, 'SITE_URL', 'http://localhost:8000')

    items = [
        {
            'id':         str(detalle.producto.id),
            'title':      detalle.producto.nombre,
            'quantity':   detalle.cantidad,
            'unit_price': float(detalle.precio_unitario),
            'currency_id': 'PEN',
        }
        for detalle in venta.detalles.select_related('producto').all()
    ]

    preferencia = {
        'items': items,
        'external_reference': venta.numero_venta,
        'back_urls': {
            'success': f'{base}/pago/exitoso',
            'failure': f'{base}/pago/fallido',
            'pending': f'{base}/pago/pendiente',
        },
        'notification_url': f'{base}/api/pagos/webhook/',
    }

    resultado = sdk.preference().create(preferencia)
    if resultado['status'] == 201:
        return resultado['response']
    raise Exception(f"Error Mercado Pago: {resultado['response']}")