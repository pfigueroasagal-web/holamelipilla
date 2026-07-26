#!/usr/bin/env python3
"""
actualizar_turno.py — Genera turno.json con la farmacia de turno de Melipilla.

Corre en GitHub Actions (que SÍ tiene internet, sin las trabas de CORS del
navegador), consulta la API del MINSAL y guarda el resultado en turno.json.
La web luego lee ese archivo desde el mismo dominio: instantáneo y confiable.

No requiere secrets. Si el MINSAL no responde, conserva el turno.json anterior
(no lo sobreescribe con datos vacíos).
"""

import json
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MINSAL_API = "https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php"
SALIDA = "turno.json"
TZ = ZoneInfo("America/Santiago")


def sin_tildes(s):
    s = (s or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def obtener_datos():
    req = urllib.request.Request(
        MINSAL_API,
        headers={"User-Agent": "Mozilla/5.0 (HolaMelipilla-turno/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def main():
    try:
        data = obtener_datos()
    except Exception as e:
        print(f"⚠ No se pudo consultar el MINSAL: {e}")
        print("Se conserva el turno.json anterior (si existe).")
        return 0

    if not isinstance(data, list):
        print("⚠ Respuesta inesperada del MINSAL. No se actualiza.")
        return 0

    melipilla = [f for f in data
                 if "melipilla" in sin_tildes(f.get("comuna_nombre", ""))]

    if not melipilla:
        print("⚠ Sin farmacias de turno para Melipilla ahora. No se sobreescribe.")
        return 0

    farmacias = []
    for f in melipilla:
        farmacias.append({
            "nombre": (f.get("local_nombre") or "").strip().title(),
            "direccion": (f.get("local_direccion") or "").strip(),
            "telefono": (f.get("local_telefono") or "").strip(),
            "apertura": (f.get("funcionamiento_hora_apertura") or "").strip(),
            "cierre": (f.get("funcionamiento_hora_cierre") or "").strip(),
        })

    ahora = datetime.now(TZ)
    salida = {
        "fecha": ahora.strftime("%Y-%m-%d"),
        "actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "comuna": "Melipilla",
        "farmacias": farmacias,
    }

    with open(SALIDA, "w", encoding="utf-8") as fp:
        json.dump(salida, fp, ensure_ascii=False, indent=2)

    print(f"✅ {SALIDA} actualizado: {len(farmacias)} farmacia(s) de turno "
          f"para el {salida['fecha']}.")
    for f in farmacias:
        print(f"   • {f['nombre']} — {f['direccion']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
