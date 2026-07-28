#!/usr/bin/env python3
"""
actualizar_turno.py — Genera turno.json con la farmacia de turno de Melipilla.

Corre en GitHub Actions (que SÍ tiene internet, sin las trabas de CORS del
navegador), consulta la API del MINSAL y guarda el resultado en turno.json.
La web luego lee ese archivo desde el mismo dominio: instantáneo y confiable.

No requiere secrets. Si el MINSAL no responde, conserva el turno.json anterior
(no lo sobreescribe con datos vacíos).
"""

import html
import json
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

MINSAL_API = "https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php"
SALIDA = "turno.json"
INDEX = "index.html"
TZ = ZoneInfo("America/Santiago")

DIAS = ["lunes", "martes", "miércoles", "jueves",
        "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def sin_tildes(s):
    s = (s or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


SITIO_API = "https://holamelipilla.cl/api/turno"
PROXIES = [
    "https://api.allorigins.win/raw?url={}",
    "https://corsproxy.io/?url={}",
]


def _fetch_json(url, timeout=25):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (HolaMelipilla-turno/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _norm_desde_minsal(f):
    return {
        "nombre": (f.get("local_nombre") or "").strip().title(),
        "direccion": (f.get("local_direccion") or "").strip(),
        "telefono": (f.get("local_telefono") or "").strip(),
        "apertura": (f.get("funcionamiento_hora_apertura") or "").strip(),
        "cierre": (f.get("funcionamiento_hora_cierre") or "").strip(),
    }


def _norm_desde_api(f):
    return {
        "nombre": (f.get("nombre") or "").strip(),
        "direccion": (f.get("direccion") or "").strip(),
        "telefono": (f.get("telefono") or "").strip(),
        "apertura": (f.get("apertura") or "").strip(),
        "cierre": (f.get("cierre") or "").strip(),
    }


def _filtrar_melipilla(data):
    if not isinstance(data, list):
        return []
    return [f for f in data
            if "melipilla" in sin_tildes(f.get("comuna_nombre", ""))]


def obtener_farmacias():
    """Devuelve la lista de farmacias de turno de Melipilla ya normalizada,
    probando varias fuentes (como el navegador) para máxima confiabilidad:
      1) El propio endpoint /api/turno del sitio (corre en Vercel, ya filtrado).
      2) El MINSAL directo.
      3) Proxies CORS de respaldo (allorigins / corsproxy).
    Si todo falla, devuelve [] y NO se sobreescribe nada."""

    # 1) Endpoint propio del sitio (el que ya usa la portada y funciona)
    try:
        d = _fetch_json(SITIO_API, 15)
        if isinstance(d, dict) and d.get("farmacias"):
            print("  · Fuente: /api/turno del sitio")
            return [_norm_desde_api(f) for f in d["farmacias"]]
    except Exception as e:
        print(f"  · /api/turno no disponible: {e}")

    # 2) MINSAL directo
    try:
        mel = _filtrar_melipilla(_fetch_json(MINSAL_API, 25))
        if mel:
            print("  · Fuente: MINSAL directo")
            return [_norm_desde_minsal(f) for f in mel]
    except Exception as e:
        print(f"  · MINSAL directo falló: {e}")

    # 3) Proxies CORS de respaldo
    for plantilla in PROXIES:
        url = plantilla.format(quote(MINSAL_API, safe=""))
        try:
            mel = _filtrar_melipilla(_fetch_json(url, 25))
            if mel:
                print(f"  · Fuente: proxy {plantilla.split('/')[2]}")
                return [_norm_desde_minsal(f) for f in mel]
        except Exception as e:
            print(f"  · Proxy {plantilla.split('/')[2]} falló: {e}")

    # 4) allorigins /get (envuelve la respuesta en {contents})
    try:
        d = _fetch_json(
            "https://api.allorigins.win/get?url=" + quote(MINSAL_API, safe=""), 25)
        contents = d.get("contents") if isinstance(d, dict) else None
        if contents:
            data = json.loads(contents) if isinstance(contents, str) else contents
            mel = _filtrar_melipilla(data)
            if mel:
                print("  · Fuente: proxy allorigins/get")
                return [_norm_desde_minsal(f) for f in mel]
    except Exception as e:
        print(f"  · allorigins/get falló: {e}")

    return []


def _fecha_larga(dt):
    return f"{DIAS[dt.weekday()]}, {dt.day} de {MESES[dt.month - 1]}"


def _es_24hrs(apertura, cierre):
    a = (apertura or "").lower().replace(" ", "")
    c = (cierre or "").lower().replace(" ", "")
    return "00:00" in a and ("00:00" in c or "23:59" in c)


def construir_html_turno(farmacias, dt):
    """Genera el mismo marcado que produce el JS, para que el turno quede
    escrito en el HTML (SEO) y se vea al instante sin esperar el JavaScript."""
    partes = []
    for f in farmacias:
        apertura, cierre = f["apertura"], f["cierre"]
        h24 = _es_24hrs(apertura, cierre)
        if apertura and cierre:
            horario = f"{apertura} – {cierre}" + (" (24 hrs)" if h24 else "")
        else:
            horario = "24 hrs"
        nombre = html.escape(f["nombre"] or "Farmacia de turno")
        direccion = html.escape(f["direccion"] or "")
        telefono = html.escape(f["telefono"] or "")
        tel_clean = "".join((f["telefono"] or "").split())
        mapa = "https://maps.google.com/?q=" + quote(
            f"{f['nombre']} {f['direccion']} Melipilla")
        badge = ' <span class="mt-24">🌙 24 hrs</span>' if h24 else ""

        acciones = ""
        if f["telefono"]:
            acciones += (f'<a href="tel:{tel_clean}" '
                         f'class="mt-btn mt-btn-primario">📞 Llamar {telefono}</a>')
        acciones += (f'<a href="{mapa}" target="_blank" rel="noopener" '
                     f'class="mt-btn">🗺️ Cómo llegar</a>')

        partes.append(
            '<div class="mt-farm">'
            f'<div class="mt-nombre">🟢 {nombre}{badge}</div>'
            + (f'<div class="mt-linea">📍 {direccion}</div>' if direccion else "")
            + f'<div class="mt-linea">🕐 {horario}</div>'
            f'<div class="mt-actions">{acciones}</div>'
            '</div>'
        )
    partes.append(f'<div class="mt-fecha">Turno del {_fecha_larga(dt)}</div>')
    return "".join(partes)


def actualizar_index(bloque_html):
    """Reemplaza el contenido entre los marcadores TURNO:INICIO y TURNO:FIN
    dentro de index.html. Nunca rompe el archivo: si no encuentra los
    marcadores, no toca nada."""
    try:
        with open(INDEX, encoding="utf-8") as fp:
            doc = fp.read()
    except FileNotFoundError:
        print(f"⚠ No se encontró {INDEX}; no se actualiza el HTML del turno.")
        return

    m_ini, m_fin = "<!-- TURNO:INICIO", "<!-- TURNO:FIN -->"
    p, q = doc.find(m_ini), doc.find(m_fin)
    if p == -1 or q == -1:
        print("⚠ Marcadores TURNO no encontrados en index.html. No se actualiza el HTML.")
        return
    cierre_ini = doc.find("-->", p)
    if cierre_ini == -1 or cierre_ini > q:
        print("⚠ Marcador TURNO:INICIO mal formado. No se actualiza el HTML.")
        return

    comentario_ini = doc[p:cierre_ini + 3]  # conserva el comentario INICIO
    nuevo = (doc[:p]
             + comentario_ini + "\n        "
             + bloque_html + "\n        "
             + doc[q:])
    if nuevo != doc:
        with open(INDEX, "w", encoding="utf-8") as fp:
            fp.write(nuevo)
        print("✅ index.html actualizado con el turno (para SEO y carga instantánea).")
    else:
        print("• index.html ya tenía el turno al día.")


def main():
    print("Buscando la farmacia de turno de Melipilla…")
    farmacias = obtener_farmacias()

    if not farmacias:
        print("⚠ Ninguna fuente entregó el turno de Melipilla ahora. "
              "No se sobreescribe (se conserva lo anterior si existe).")
        return 0

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

    # Inyecta el turno en index.html para que Google lo indexe y se vea al
    # instante. Protegido: si algo falla, no interrumpe la actualización.
    try:
        actualizar_index(construir_html_turno(farmacias, ahora))
    except Exception as e:
        print(f"⚠ No se pudo actualizar el HTML del turno en index.html: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
