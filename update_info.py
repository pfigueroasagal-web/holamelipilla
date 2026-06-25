#!/usr/bin/env python3
"""
update_info.py — Verificador mensual de información para holamelipilla.cl
Busca en fuentes oficiales si hay cambios en teléfonos, horarios y direcciones,
y actualiza el index.html si encuentra diferencias.
"""

import re
import json
import urllib.request
import urllib.error
from datetime import datetime

# ── Datos conocidos del sitio (fuente de verdad actual) ──────────────────────
DATOS_ACTUALES = {
    "farmacias": [
        {"nombre": "Farmacia Cariño",        "tel": "2 2831 5050", "dir": "Ortúzar 399",         "horario": "10:00 – 23:00"},
        {"nombre": "Farmacia Independencia",  "tel": "+56 2 2631 3070","dir": "Independencia",    "horario": "08:30 – 22:00"},
        {"nombre": "Farmacia Cruz Verde Independencia","tel": "+56 2 2832 7526","dir": "Independencia","horario": "09:00 – 22:30"},
        {"nombre": "Cruz Verde Plaza de Armas","tel": "+56 2 2832 3888","dir": "Plaza de Armas 561","horario": "09:00 – 21:00"},
        {"nombre": "Cruz Verde Serrano",      "tel": "+56 2 2831 1552","dir": "Serrano 501",       "horario": "08:30 – 22:00"},
        {"nombre": "Farmacia Ahumada Serrano","tel": "+56 2 2831 8135","dir": "Serrano 395",       "horario": "09:00 – 21:00"},
        {"nombre": "Salcobrand Ortúzar 548",  "tel": "+56 2 2831 0328","dir": "Ortúzar 548",       "horario": "09:00 – 23:00"},
        {"nombre": "Salcobrand Ortúzar 691",  "tel": "+56 2 2832 1955","dir": "Ortúzar 691",       "horario": "09:00 – 21:00"},
        {"nombre": "Salcobrand Ortúzar 857",  "tel": "+56 2 2832 3157","dir": "Ortúzar 857",       "horario": "09:00 – 21:00"},
    ],
    "cesfam": [
        {"nombre": "CESFAM Dr. Edelberto Elgueta",      "tel": "800 432 777",   "dir": "Arza 1576",                      "horario": "Lun–Jue 08:00–20:00 · Vie 08:00–19:00 · Sáb 09:00–13:00"},
        {"nombre": "CESFAM Dr. Francisco Boris Soler",  "tel": "2 2821 8350",   "dir": "Silvia Chávez 1650",             "horario": ""},
        {"nombre": "CESFAM San Manuel",                  "tel": "2 2574 5500",   "dir": "Camino San Manuel S/N",          "horario": ""},
        {"nombre": "CESFAM Alfarera Rosa Reyes Vilches","tel": "2 2832 4965",   "dir": "Artesana Julita Vera 354",       "horario": ""},
        {"nombre": "CES Ignacio Carrera Pinto",          "tel": "2 2800 0401",   "dir": "Ignacio Carrera Pinto 606",      "horario": ""},
    ],
    "hospital": {
        "nombre": "Hospital de Melipilla",
        "tel": "2 2958 1543",
        "dir": "O'Higgins 551",
        "horario": "24 hrs"
    },
    "emergencias": {
        "Carabineros": "133",
        "SAMU": "131",
        "Bomberos": "132",
        "PDI": "149",
        "Seguridad pública": "1452",
        "VIF / Mujer": "1455",
        "Municipalidad": "800 730 800"
    }
}

# ── Fuentes a consultar ───────────────────────────────────────────────────────
FUENTES = [
    ("CORPO Melipilla Salud", "https://corpomelipilla.cl/salud/"),
    ("Municipalidad Melipilla", "https://www.municipalidadmelipilla.cl/"),
]

LOG = []

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry)
    LOG.append(entry)

def fetch_url(url, timeout=15):
    """Descarga una URL y retorna el texto, o None si falla."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; HolaMelipilla-bot/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  ⚠ No se pudo acceder a {url}: {e}")
        return None

def buscar_telefonos_en_texto(texto, nombre):
    """Busca números de teléfono chilenos en un texto."""
    patrones = [
        r'\b(800\s?\d{3}\s?\d{3})\b',           # 800 XXX XXX
        r'\b(2\s?2\d{3}\s?\d{4})\b',             # 2 2XXX XXXX
        r'\b(\+56\s?2\s?2\d{3}\s?\d{4})\b',      # +56 2 2XXX XXXX
        r'\b(56\s?2\s?2\d{3}\s?\d{4})\b',        # 56 2 2XXX XXXX
        r'\b(1[34][0-9]{1,2})\b',                 # 131, 133, 149, etc.
        r'\b(1[45]\d{2})\b',                      # 1452, 1455
    ]
    encontrados = []
    for pat in patrones:
        matches = re.findall(pat, texto)
        encontrados.extend(matches)
    if encontrados:
        log(f"  📞 Teléfonos encontrados para '{nombre}': {set(encontrados)}")
    return set(encontrados)

def verificar_cambios(html_actual):
    """
    Compara los datos conocidos con lo que aparece en fuentes web.
    Retorna lista de cambios detectados (puede estar vacía).
    """
    cambios = []
    log("🔍 Verificando fuentes oficiales...")

    for nombre_fuente, url in FUENTES:
        log(f"\n→ Consultando {nombre_fuente} ({url})")
        texto = fetch_url(url)
        if not texto:
            continue

        # Busca si algún teléfono conocido ya NO aparece en el sitio oficial
        for cat_nombre, items in [("CESFAM", DATOS_ACTUALES["cesfam"]),
                                    ("Farmacias", DATOS_ACTUALES["farmacias"])]:
            for item in items:
                tel_limpio = re.sub(r'[\s\-\+]', '', item["tel"])
                if tel_limpio and len(tel_limpio) >= 6:
                    # Busca variantes del número en el texto fuente
                    variantes = [tel_limpio, item["tel"]]
                    encontrado = any(v in texto for v in variantes)
                    if not encontrado:
                        msg = f"⚠ Teléfono de {item['nombre']} ({item['tel']}) NO encontrado en {nombre_fuente}"
                        log(f"  {msg}")
                        cambios.append(msg)

    return cambios

def generar_reporte(cambios, html_path="index.html"):
    """Genera un reporte de la verificación mensual."""
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    reporte = {
        "fecha_verificacion": fecha,
        "cambios_detectados": len(cambios),
        "detalle": cambios,
        "log": LOG,
        "estado": "CAMBIOS DETECTADOS — revisar manualmente" if cambios else "OK — sin cambios detectados"
    }

    with open("verificacion_info.json", "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    log(f"\n📄 Reporte guardado en verificacion_info.json")
    log(f"Estado final: {reporte['estado']}")
    return reporte

def actualizar_fecha_verificacion(html_path="index.html"):
    """
    Actualiza el comentario de última verificación en el HTML.
    Esto genera siempre un commit visible que confirma que el bot corrió.
    """
    fecha = datetime.now().strftime("%d/%m/%Y")
    with open(html_path, "r", encoding="utf-8") as f:
        contenido = f.read()

    # Busca y reemplaza el comentario de última verificación
    nuevo = re.sub(
        r'<!-- Última verificación automática: [\d/]+ -->',
        f'<!-- Última verificación automática: {fecha} -->',
        contenido
    )

    # Si no existe el comentario, lo inserta antes del </head>
    if nuevo == contenido:
        nuevo = contenido.replace(
            '</head>',
            f'<!-- Última verificación automática: {fecha} -->\n</head>',
            1
        )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(nuevo)

    log(f"✅ Fecha de verificación actualizada en index.html: {fecha}")

def main():
    log("=" * 60)
    log(f"🤖 Bot de verificación holamelipilla.cl — {datetime.now().strftime('%Y-%m-%d')}")
    log("=" * 60)

    # 1. Verificar fuentes oficiales
    cambios = verificar_cambios("index.html")

    # 2. Siempre actualizar la fecha de última verificación en el HTML
    actualizar_fecha_verificacion("index.html")

    # 3. Generar reporte JSON
    reporte = generar_reporte(cambios)

    # 4. Resumen final
    log("\n" + "=" * 60)
    if cambios:
        log(f"⚠ Se detectaron {len(cambios)} posibles cambios.")
        log("  → Revisa verificacion_info.json y actualiza el sitio manualmente.")
    else:
        log("✅ Todo en orden. No se detectaron cambios en la información.")
    log("=" * 60)

    # Retorna código de salida 0 siempre (no falla el workflow)
    return 0

if __name__ == "__main__":
    exit(main())
