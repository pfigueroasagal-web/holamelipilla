// api/turno.js — Función serverless de Vercel.
// Entrega la farmacia de turno de Melipilla en JSON, consultando el MINSAL
// DESDE EL SERVIDOR (sin las trabas de CORS del navegador). La portada la lee
// desde /api/turno y, si falla, cae a sus propios respaldos.
//
// Robustez: prueba VARIOS endpoints oficiales (farmanet clásico y midas nuevo)
// y hace un match flexible del nombre de comuna, porque el campo varía según
// el endpoint. No requiere secrets. Vercel la detecta automáticamente.

const ENDPOINTS = [
  'https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php',
  'https://farmanet.minsal.cl/maps/index.php/ws/getLocalesTurnos',
  'http://farmanet.minsal.cl/maps/index.php/ws/getLocalesTurnos',
];

// Cabeceras que imitan a un navegador real (Chrome). Muchos 403 del MINSAL se
// deben a que el request "no parece" un navegador; esto suele evitarlo.
const NAVEGADOR = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  'Accept': 'application/json, text/javascript, */*; q=0.01',
  'Accept-Language': 'es-CL,es;q=0.9,en;q=0.8',
  'X-Requested-With': 'XMLHttpRequest',
  'Referer': 'https://farmanet.minsal.cl/',
};

function sinTildes(s) {
  return (s || '').toString().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function fechaSantiago() {
  const d = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Santiago' }));
  return d.getFullYear() + '-' +
    String(d.getMonth() + 1).padStart(2, '0') + '-' +
    String(d.getDate()).padStart(2, '0');
}

// El nombre de comuna viene en campos distintos según el endpoint.
function comunaDe(f) {
  return f.comuna_nombre || f.comuna || f.nombre_comuna || f.localidad_nombre || f.localidad || '';
}

async function traer(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: NAVEGADOR });
    clearTimeout(timer);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    return Array.isArray(data) ? data : [];
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}

module.exports = async function handler(req, res) {
  const diag = [];

  for (const url of ENDPOINTS) {
    const host = url.split('/')[2];
    try {
      const data = await traer(url);
      const mel = data.filter(function (f) {
        return sinTildes(comunaDe(f)).indexOf('melipilla') >= 0;
      });
      if (mel.length) {
        const farmacias = mel.map(function (f) {
          return {
            nombre: (f.local_nombre || '').trim(),
            direccion: (f.local_direccion || '').trim(),
            telefono: (f.local_telefono || '').trim(),
            apertura: (f.funcionamiento_hora_apertura || '').trim(),
            cierre: (f.funcionamiento_hora_cierre || '').trim(),
          };
        });
        // Cache en el CDN de Vercel: 30 min fresco + 1 día sirviendo mientras revalida
        res.setHeader('Cache-Control', 'public, s-maxage=1800, stale-while-revalidate=86400');
        return res.status(200).json({ fecha: fechaSantiago(), farmacias: farmacias, fuente: host });
      }
      diag.push(host + ': 200 sin Melipilla (' + data.length + ' locales)');
    } catch (e) {
      diag.push(host + ': ' + String((e && e.message) || e));
    }
  }

  // Ninguna fuente devolvió Melipilla: no cacheamos mucho para reintentar pronto.
  res.setHeader('Cache-Control', 'public, s-maxage=120');
  res.status(200).json({ fecha: fechaSantiago(), farmacias: [], diagnostico: diag });
};
