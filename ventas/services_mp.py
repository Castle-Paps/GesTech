import mercadopago
from django.conf import settings


import mercadopago
from django.conf import settings


def crear_preferencia(venta):
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

    items = []
    for detalle in venta.detalles.all():
        items.append({
            'id':          str(detalle.producto.id),
            'title':       detalle.producto.nombre,
            'quantity':    detalle.cantidad,
            'unit_price':  float(detalle.precio_unitario),
            'currency_id': 'PEN',
        })

    preferencia = {
        'items': items,
        'external_reference': venta.numero_venta,
        'payer': {
            'email': 'TESTUSER3302873853@testuser.com',
        },
        # ← reemplaza con tu URL de ngrok
        'notification_url': 'https://nonclarifiable-unpolitely-jaunita.ngrok-free.dev',
    }

    resultado = sdk.preference().create(preferencia)

    if resultado['status'] == 201:
        return resultado['response']
    else:
        raise Exception(f"Error Mercado Pago: {resultado['response']}")

"""def crear_preferencia(venta):
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

    # Construye los items desde los detalles de la venta
    items = []
    for detalle in venta.detalles.all():
        items.append({
            'id':          str(detalle.producto.id),
            'title':       detalle.producto.nombre,
            'quantity':    detalle.cantidad,
            'unit_price':  float(detalle.precio_unitario),
            'currency_id': 'PEN',
        })

    preferencia = {
        'items': items,
        # external_reference identifica la venta cuando MP nos notifica
        'external_reference': venta.numero_venta,
        'back_urls': {
            'success': 'http://localhost:5173/pago/exitoso',
            'failure': 'http://localhost:5173/pago/fallido',
            'pending': 'http://localhost:5173/pago/pendiente',
        },
        'auto_return': 'approved',
    }

    resultado = sdk.preference().create(preferencia)

    if resultado['status'] == 201:
        return resultado['response']
    else:
        raise Exception(f"Error Mercado Pago: {resultado['response']}")"""