// api/turno.js — Función serverless de Vercel.
// Consulta la farmacia de turno de Melipilla en el MINSAL DESDE EL SERVIDOR
// (sin las trabas de CORS del navegador ni proxies inestables) y la entrega
// como JSON al mismo dominio. La portada la lee desde /api/turno.
//
// No requiere secrets ni GitHub Actions. Vercel la detecta automáticamente.

const API_URL = 'https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php';

function sinTildes(s) {
  return (s || '').toString().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function fechaSantiago() {
  const d = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Santiago' }));
  return d.getFullYear() + '-' +
    String(d.getMonth() + 1).padStart(2, '0') + '-' +
    String(d.getDate()).padStart(2, '0');
}

module.exports = async function handler(req, res) {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    const r = await fetch(API_URL, {
      signal: ctrl.signal,
      headers: { 'User-Agent': 'Mozilla/5.0 (HolaMelipilla/1.0)' }
    });
    clearTimeout(timer);
    if (!r.ok) throw new Error('HTTP ' + r.status);

    const data = await r.json();
    const mel = (Array.isArray(data) ? data : []).filter(function (f) {
      return sinTildes(f.comuna_nombre || f.comuna || '').indexOf('melipilla') >= 0;
    });

    const farmacias = mel.map(function (f) {
      return {
        nombre: (f.local_nombre || '').trim(),
        direccion: (f.local_direccion || '').trim(),
        telefono: (f.local_telefono || '').trim(),
        apertura: (f.funcionamiento_hora_apertura || '').trim(),
        cierre: (f.funcionamiento_hora_cierre || '').trim()
      };
    });

    // Cache en el CDN de Vercel: 1 h fresco + 1 día sirviendo mientras revalida
    res.setHeader('Cache-Control', 'public, s-maxage=3600, stale-while-revalidate=86400');
    res.status(200).json({ fecha: fechaSantiago(), farmacias: farmacias });
  } catch (e) {
    // No cacheamos errores mucho tiempo, para reintentar pronto
    res.setHeader('Cache-Control', 'public, s-maxage=120');
    res.status(200).json({ fecha: '', farmacias: [], error: String(e && e.message || e) });
  }
};
