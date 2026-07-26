#!/usr/bin/env python3
"""
enviar_push.py — Envía la notificación diaria del turno de farmacia.

Corre en GitHub Actions (ver .github/workflows/push-diario.yml).
1. Lee la farmacia de turno de hoy en Melipilla desde la API del MINSAL.
2. Lee las suscripciones push guardadas en Supabase.
3. Envía una notificación Web Push a cada vecino suscrito.
4. Borra las suscripciones que ya no existen (410/404).

Requiere (secrets de GitHub Actions):
  SUPABASE_URL           URL del proyecto Supabase
  SUPABASE_SERVICE_KEY   clave service_role (¡secreta! bypassa RLS)
  VAPID_PUBLIC_KEY       clave pública VAPID
  VAPID_PRIVATE_KEY      clave privada VAPID
  VAPID_SUBJECT          mailto:tu-correo@ejemplo.cl
"""

import os
import sys
import json
import unicodedata
import urllib.request
import urllib.error

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    print("Falta pywebpush. Instala con: pip install pywebpush")
    sys.exit(1)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
VAPID_PUBLIC = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIV   = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:contacto@holamelipilla.cl")

MINSAL_API = "https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php"


def sin_tildes(s):
    s = (s or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def http_json(url, method="GET", headers=None, data=None):
    headers = headers or {}
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, method=method, headers=headers, data=body)
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else None


def obtener_turno():
    """Devuelve el texto de la farmacia de turno de hoy en Melipilla."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (HolaMelipilla-push/1.0)"}
        data = http_json(MINSAL_API, headers=headers)
    except Exception as e:
        print(f"No se pudo leer el turno del MINSAL: {e}")
        return None

    melipilla = [f for f in (data or [])
                 if "melipilla" in sin_tildes(f.get("comuna_nombre", ""))]
    if not melipilla:
        return None

    f = melipilla[0]
    nombre = f.get("local_nombre", "Farmacia de turno").title()
    direccion = f.get("local_direccion", "")
    return {
        "nombre": nombre,
        "direccion": direccion,
        "total": len(melipilla),
    }


def leer_suscripciones():
    url = f"{SUPABASE_URL}/rest/v1/push_subs?select=*"
    headers = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    return http_json(url, headers=headers) or []


def borrar_suscripcion(endpoint):
    from urllib.parse import quote
    url = f"{SUPABASE_URL}/rest/v1/push_subs?endpoint=eq.{quote(endpoint, safe='')}"
    headers = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    try:
        http_json(url, method="DELETE", headers=headers)
    except Exception:
        pass


def main():
    faltan = [k for k, v in {
        "SUPABASE_URL": SUPABASE_URL, "SUPABASE_SERVICE_KEY": SERVICE_KEY,
        "VAPID_PUBLIC_KEY": VAPID_PUBLIC, "VAPID_PRIVATE_KEY": VAPID_PRIV,
    }.items() if not v]
    if faltan:
        print("Faltan variables de entorno:", ", ".join(faltan))
        sys.exit(1)

    turno = obtener_turno()
    if not turno:
        print("Sin datos de turno hoy — no se envía nada.")
        return 0

    cuerpo = f"Hoy: {turno['nombre']}"
    if turno["direccion"]:
        cuerpo += f" — {turno['direccion']}"
    payload = json.dumps({
        "title": "💊 Farmacia de turno en Melipilla",
        "body": cuerpo,
        "tag": "turno-diario",
        "url": "https://holamelipilla.cl/#farmacias",
    })

    subs = leer_suscripciones()
    print(f"Enviando a {len(subs)} suscriptores…")
    ok, fail = 0, 0
    for s in subs:
        info = {"endpoint": s["endpoint"],
                "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}}
        try:
            webpush(
                subscription_info=info,
                data=payload,
                vapid_private_key=VAPID_PRIV,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
            ok += 1
        except WebPushException as e:
            fail += 1
            code = getattr(e.response, "status_code", None)
            if code in (404, 410):
                borrar_suscripcion(s["endpoint"])
                print(f"  Suscripción vencida eliminada ({code}).")
            else:
                print(f"  Error enviando: {e}")

    print(f"Listo. Enviadas: {ok} · Fallidas: {fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
