"""
pagos/views.py
Endpoints Django para crear pagos y recibir webhooks de Mercado Pago.
"""
import json
import logging

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from . import services

logger = logging.getLogger(__name__)


# ─── Crear pago ──────────────────────────────────────────────────────────────

class CrearPagoView(View):
    """
    POST /pagos/crear/
    Body JSON:
    {
        "token": "TOKEN_GENERADO_POR_CARDFORM",
        "monto": 1500.00,
        "descripcion": "Producto XYZ",
        "email": "comprador@email.com",
        "cuotas": 1,
        "id_externo": "orden-42"   ← opcional, tu propio ID
    }
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)

        # Validar campos requeridos
        requeridos = ("token", "monto", "descripcion", "email")
        faltantes = [c for c in requeridos if not body.get(c)]
        if faltantes:
            return JsonResponse(
                {"error": f"Campos requeridos: {', '.join(faltantes)}"}, status=400
            )

        resultado = services.crear_pago(
            token=body["token"],
            monto=body["monto"],
            descripcion=body["descripcion"],
            email_pagador=body["email"],
            cuotas=int(body.get("cuotas", 1)),
            id_externo=body.get("id_externo"),
        )

        if not resultado["ok"]:
            return JsonResponse(
                {
                    "error": "Pago rechazado o fallido",
                    "status": resultado["status"],
                    "status_detail": resultado["status_detail"],
                },
                status=422,
            )

        return JsonResponse(
            {
                "payment_id": resultado["payment_id"],
                "status": resultado["status"],
                "status_detail": resultado["status_detail"],
            },
            status=201,
        )


# ─── Consultar pago ──────────────────────────────────────────────────────────

class ConsultarPagoView(View):
    """
    GET /pagos/<payment_id>/
    """

    def get(self, request, payment_id):
        resultado = services.consultar_pago(payment_id)
        if not resultado["ok"]:
            return JsonResponse({"error": "Pago no encontrado"}, status=404)
        return JsonResponse(
            {"status": resultado["status"], "status_detail": resultado["status_detail"]}
        )


# ─── Webhook ─────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class WebhookView(View):
    """
    POST /pagos/webhook/

    Mercado Pago envía una notificación cada vez que cambia el estado
    de un pago. Este endpoint valida la firma y procesa el evento.

    Configura la URL en:
    https://www.mercadopago.com/developers/panel → Tu integración → Webhooks
    """

    def post(self, request):
        # 1. Leer cabeceras de seguridad
        x_signature = request.headers.get("x-signature", "")
        x_request_id = request.headers.get("x-request-id", "")

        # 2. Parsear cuerpo
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)

        data_id = str(payload.get("data", {}).get("id", ""))

        # 3. Validar firma HMAC
        if x_signature and not services.validar_firma_webhook(
            x_signature, x_request_id, data_id
        ):
            logger.warning("Webhook MP: firma inválida rechazada.")
            return JsonResponse({"error": "Firma inválida"}, status=403)

        # 4. Procesar según el tipo de evento
        tipo = payload.get("type")
        logger.info("Webhook MP recibido: type=%s data_id=%s", tipo, data_id)

        if tipo == "payment":
            self._procesar_pago(data_id)

        # Siempre responde 200 para que MP no reintente
        return JsonResponse({"ok": True}, status=200)

    def _procesar_pago(self, payment_id: str):
        """Consulta el pago actualizado y aplica lógica de negocio."""
        resultado = services.consultar_pago(payment_id)
        if not resultado["ok"]:
            logger.error("No se pudo consultar pago %s en webhook", payment_id)
            return

        status = resultado["status"]
        logger.info("Pago %s → status=%s detail=%s", payment_id, status, resultado["status_detail"])

        # ── Aquí va tu lógica de negocio ────────────────────────────────────
        if status == "approved":
            # Ej: marcar orden como pagada en tu BD
            # Orden.objects.filter(payment_id=payment_id).update(estado="pagada")
            logger.info("✅ Pago %s APROBADO — activar servicio/orden", payment_id)

        elif status == "pending":
            logger.info("⏳ Pago %s PENDIENTE — esperando confirmación", payment_id)

        elif status in ("rejected", "cancelled"):
            logger.warning("❌ Pago %s %s — notificar al usuario", payment_id, status)
        # ────────────────────────────────────────────────────────────────────