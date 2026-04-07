"""
pagos/services.py
Capa de servicio que encapsula toda la lógica de Mercado Pago.
"""
import hashlib
import hmac
import logging

import mercadopago
from django.conf import settings

logger = logging.getLogger(__name__)

# Cliente SDK reutilizable (singleton por proceso)
_sdk = None


def get_sdk() -> mercadopago.SDK:
    global _sdk
    if _sdk is None:
        _sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    return _sdk


# ─── Pagos ───────────────────────────────────────────────────────────────────

def crear_pago(
    token: str,
    monto: float,
    descripcion: str,
    email_pagador: str,
    cuotas: int = 1,
    id_externo: str = None,
) -> dict:
    """
    Crea un pago directo con un token de tarjeta generado por el frontend
    (MercadoPago.js / CardForm).

    Parámetros:
        token        – Token de tarjeta devuelto por el SDK de JS.
        monto        – Monto total a cobrar (float).
        descripcion  – Texto que verá el comprador en su resumen.
        email_pagador– Email del comprador.
        cuotas       – Número de cuotas (installments).
        id_externo   – ID propio de tu sistema para identificar el pago.

    Retorna:
        dict con 'ok' (bool), 'status', 'status_detail', 'payment_id' y 'raw'.
    """
    sdk = get_sdk()

    payload = {
        "token": token,
        "transaction_amount": float(monto),
        "description": descripcion,
        "installments": cuotas,
        "payment_method_id": None,  # MP lo infiere del token automáticamente
        "payer": {"email": email_pagador},
    }

    if id_externo:
        payload["external_reference"] = str(id_externo)

    respuesta = sdk.payment().create(payload)
    data = respuesta.get("response", {})
    status_code = respuesta.get("status")

    if status_code not in (200, 201):
        logger.error("MP crear_pago error %s: %s", status_code, data)
        return {
            "ok": False,
            "status": data.get("status"),
            "status_detail": data.get("status_detail"),
            "payment_id": None,
            "raw": data,
        }

    logger.info("Pago creado id=%s status=%s", data.get("id"), data.get("status"))
    return {
        "ok": True,
        "status": data.get("status"),           # approved / pending / rejected
        "status_detail": data.get("status_detail"),
        "payment_id": data.get("id"),
        "raw": data,
    }


def consultar_pago(payment_id: int | str) -> dict:
    """Consulta el estado actual de un pago por su ID de Mercado Pago."""
    sdk = get_sdk()
    respuesta = sdk.payment().get(payment_id)
    data = respuesta.get("response", {})
    return {
        "ok": respuesta.get("status") == 200,
        "status": data.get("status"),
        "status_detail": data.get("status_detail"),
        "raw": data,
    }


def reembolsar_pago(payment_id: int | str, monto: float = None) -> dict:
    """
    Reembolsa un pago total o parcialmente.
    Si monto=None → reembolso total.
    """
    sdk = get_sdk()
    payload = {}
    if monto is not None:
        payload["amount"] = float(monto)

    respuesta = sdk.payment().refund(payment_id, payload)
    data = respuesta.get("response", {})
    ok = respuesta.get("status") in (200, 201)
    if not ok:
        logger.error("MP reembolso error pago=%s: %s", payment_id, data)
    return {"ok": ok, "raw": data}


# ─── Webhook ─────────────────────────────────────────────────────────────────

def validar_firma_webhook(x_signature: str, x_request_id: str, data_id: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 que Mercado Pago envía en la cabecera
    'x-signature' para garantizar que la notificación es auténtica.

    Documentación: https://www.mercadopago.com/developers/es/docs/your-integrations/notifications/webhooks
    """
    secret = settings.MERCADOPAGO_WEBHOOK_SECRET
    if not secret:
        logger.warning("MP_WEBHOOK_SECRET no configurado; firma no validada.")
        return True  # Cambia a False en producción si quieres bloquear sin firma

    # Construir el mensaje tal como indica la documentación de MP
    # ts= viene en x-signature como "ts=TIMESTAMP,v1=HASH"
    parts = {k: v for k, v in (p.split("=", 1) for p in x_signature.split(","))}
    ts = parts.get("ts", "")
    firma_recibida = parts.get("v1", "")

    mensaje = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    firma_esperada = hmac.new(secret.encode(), mensaje.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(firma_esperada, firma_recibida)