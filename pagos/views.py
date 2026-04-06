from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views import View
from ventas.models import Venta, Recibo
import json
import logging

logger = logging.getLogger(__name__)

from . import services


class CrearPagoView(View):
    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)

        requeridos = ("token", "monto", "descripcion", "email")
        faltantes  = [c for c in requeridos if not body.get(c)]
        if faltantes:
            return JsonResponse(
                {"error": f"Campos requeridos: {', '.join(faltantes)}"}, status=400
            )

        resultado = services.crear_pago(
            token         = body["token"],
            monto         = body["monto"],
            descripcion   = body["descripcion"],
            email_pagador = body["email"],
            cuotas        = int(body.get("cuotas", 1)),
            id_externo    = body.get("id_externo"),
        )

        if not resultado["ok"]:
            return JsonResponse(
                {
                    "error":         "Pago rechazado o fallido",
                    "status":        resultado["status"],
                    "status_detail": resultado["status_detail"],
                },
                status=422,
            )

        return JsonResponse(
            {
                "payment_id":    resultado["payment_id"],
                "status":        resultado["status"],
                "status_detail": resultado["status_detail"],
            },
            status=201,
        )


class ConsultarPagoView(View):
    def get(self, request, payment_id):
        resultado = services.consultar_pago(payment_id)
        if not resultado["ok"]:
            return JsonResponse({"error": "Pago no encontrado"}, status=404)
        return JsonResponse(
            {"status": resultado["status"], "status_detail": resultado["status_detail"]}
        )


@method_decorator(csrf_exempt, name="dispatch")
class WebhookView(View):
    def post(self, request):
        x_signature  = request.headers.get("x-signature", "")
        x_request_id = request.headers.get("x-request-id", "")

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)

        data_id = str(payload.get("data", {}).get("id", ""))

        if x_signature and not services.validar_firma_webhook(
            x_signature, x_request_id, data_id
        ):
            logger.warning("Webhook MP: firma inválida rechazada.")
            return JsonResponse({"error": "Firma inválida"}, status=403)

        tipo = payload.get("type")
        logger.info("Webhook MP recibido: type=%s data_id=%s", tipo, data_id)

        if tipo == "payment":
            self._procesar_pago(data_id)

        return JsonResponse({"ok": True}, status=200)

    def _procesar_pago(self, payment_id: str):
        resultado = services.consultar_pago(payment_id)
        if not resultado["ok"]:
            logger.error("No se pudo consultar pago %s en webhook", payment_id)
            return

        mp_status        = resultado["status"]
        external_ref     = resultado["raw"].get("external_reference")

        logger.info("Pago %s → status=%s", payment_id, mp_status)

        if not external_ref:
            logger.warning("Pago %s sin external_reference", payment_id)
            return

        # Busca la venta por numero_venta
        try:
            venta = Venta.objects.get(numero_venta=external_ref)
        except Venta.DoesNotExist:
            logger.error("Venta %s no encontrada", external_ref)
            return

        # Actualiza los campos de Mercado Pago
        venta.mp_payment_id = str(payment_id)
        venta.mp_status     = mp_status

        if mp_status == "approved":
            venta.estado = "completada"
            venta.save()
            logger.info("Venta %s completada", external_ref)

            # Genera el recibo automáticamente si no tiene uno
            if not hasattr(venta, 'recibo'):
                cliente_nombre = venta.cliente.nombre if venta.cliente else "Cliente General"
                ultimo = Recibo.objects.filter(
                    tipo_comprobante='ticket', serie='T001'
                ).count()
                numero = str(ultimo + 1).zfill(8)
                Recibo.objects.create(
                    venta            = venta,
                    tipo_comprobante = 'ticket',
                    serie            = 'T001',
                    numero           = numero,
                    cliente_nombre   = cliente_nombre,
                    monto_total      = venta.total,
                )
                logger.info("Recibo generado para venta %s", external_ref)

        elif mp_status in ("rejected", "cancelled"):
            venta.estado = "anulada"
            venta.save()
            logger.warning("Venta %s anulada por pago %s", external_ref, mp_status)

        else:
            # pending — guarda el estado pero no cambia la venta
            venta.save()