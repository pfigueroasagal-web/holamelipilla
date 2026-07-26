/* ══════════════════════════════════════════════════════════════════════
   config.js — Configuración central de Hola Melipilla
   ──────────────────────────────────────────────────────────────────────
   Rellena estos valores para activar las funciones de COMUNIDAD REAL
   (reportes, encuesta y visitas compartidas entre todos los vecinos),
   las REDES SOCIALES y las NOTIFICACIONES push.

   👉 Mientras estén vacíos, el sitio funciona igual que siempre usando
      almacenamiento local en el navegador. No se rompe nada.

   Guía paso a paso en SETUP.md
   ══════════════════════════════════════════════════════════════════════ */
window.HM_CONFIG = {

  /* 1) SUPABASE — backend gratis para reportes, encuesta, visitas y avisos.
        Crea un proyecto en https://supabase.com (plan free), corre el
        archivo supabase_setup.sql y pega aquí la URL y la clave "anon". */
  SUPABASE_URL: '',        // ej: 'https://abcdxyz.supabase.co'
  SUPABASE_ANON_KEY: '',   // clave pública "anon" (segura para el navegador)

  /* 2) REDES SOCIALES — pon tus enlaces reales. Si dejas uno vacío, ese
        botón se oculta automáticamente (mejor no mostrar links muertos). */
  SOCIAL: {
    instagram:     'https://www.instagram.com/holamelipilla',
    tiktok:        'https://www.tiktok.com/@holamelipilla',
    whatsappCanal: ''      // enlace a tu Canal / Comunidad de WhatsApp
  },

  /* 3) NOTIFICACIONES PUSH — clave pública VAPID (ver SETUP.md).
        La clave privada va en los secrets de GitHub Actions, NO aquí. */
  VAPID_PUBLIC_KEY: ''
};


/* ══════════════════════════════════════════════════════════════════════
   HMBackend — capa de datos unificada.
   Usa Supabase si está configurado; si no, cae a localStorage.
   El resto del sitio solo llama a window.HM.* y no le importa cuál es.
   ══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var cfg = window.HM_CONFIG || {};
  var URL = (cfg.SUPABASE_URL || '').trim().replace(/\/+$/, '');
  var KEY = (cfg.SUPABASE_ANON_KEY || '').trim();
  var ONLINE = !!(URL && KEY && URL.indexOf('http') === 0);

  /* ---------- helpers Supabase REST ---------- */
  function sb(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({
      'apikey': KEY,
      'Authorization': 'Bearer ' + KEY,
      'Content-Type': 'application/json'
    }, opts.headers || {});
    return fetch(URL + '/rest/v1' + path, opts).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error('Supabase ' + r.status + ': ' + t); });
      if (r.status === 204) return null;
      return r.text().then(function (t) { return t ? JSON.parse(t) : null; });
    });
  }
  function rpc(name, args) {
    return sb('/rpc/' + name, { method: 'POST', body: JSON.stringify(args || {}) });
  }

  /* ---------- helpers localStorage ---------- */
  function lsGet(k, def) {
    try { var v = JSON.parse(localStorage.getItem(k)); return (v === null || v === undefined) ? def : v; }
    catch (e) { return def; }
  }
  function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  /* ISO week id (mismo criterio que usaba el sitio) */
  function weekId(d) {
    var yearStart = new Date(d.getFullYear(), 0, 1);
    var week = Math.ceil(((d - yearStart) / 86400000 + yearStart.getDay() + 1) / 7);
    return d.getFullYear() + '-W' + week;
  }

  /* ════════ REPORTES VECINALES ════════ */
  var REP_KEY = 'hm_reportes_v1';
  var VENTANA_MS = 48 * 60 * 60 * 1000; // solo mostramos reportes de las últimas 48h

  var reportes = {
    /* Devuelve array normalizado: {id, tipo, sector, texto, ts, confirm, deny} */
    list: function () {
      if (ONLINE) {
        return sb('/reportes?select=*&order=created_at.desc&limit=40').then(function (rows) {
          var corte = Date.now() - VENTANA_MS;
          return (rows || []).map(function (r) {
            return {
              id: r.id, tipo: r.tipo, sector: r.sector || '', texto: r.texto,
              ts: new Date(r.created_at).getTime(),
              confirm: r.confirm || 0, deny: r.deny || 0
            };
          }).filter(function (r) { return r.ts >= corte; });
        });
      }
      return Promise.resolve(lsGet(REP_KEY, []));
    },
    add: function (r) {
      if (ONLINE) {
        return sb('/reportes', {
          method: 'POST',
          headers: { 'Prefer': 'return=representation' },
          body: JSON.stringify({ tipo: r.tipo, sector: r.sector, texto: r.texto })
        });
      }
      var items = lsGet(REP_KEY, []);
      items.unshift({
        id: 'r_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
        tipo: r.tipo, sector: r.sector, texto: r.texto,
        ts: Date.now(), confirm: 0, deny: 0
      });
      lsSet(REP_KEY, items.slice(0, 20));
      return Promise.resolve();
    },
    react: function (id, campo) {
      if (ONLINE) return rpc('incrementar_reaccion', { p_id: id, p_campo: campo });
      var items = lsGet(REP_KEY, []);
      var it = items.find(function (x) { return x.id === id; });
      if (it) { it[campo] = (it[campo] || 0) + 1; lsSet(REP_KEY, items); }
      return Promise.resolve();
    },
    remove: function (id) {
      // Borrar solo tiene sentido en modo local (tablón privado del navegador)
      if (ONLINE) return Promise.resolve();
      var items = lsGet(REP_KEY, []).filter(function (x) { return x.id !== id; });
      lsSet(REP_KEY, items);
      return Promise.resolve();
    }
  };

  /* ════════ ENCUESTA DE LA SEMANA ════════ */
  var ENC_KEY = 'hm_encuesta_v2';
  var encuesta = {
    weekId: function (dSantiago) { return weekId(dSantiago); },
    /* {opciones: {op: n, ...}, total, voted} */
    estado: function (wid) {
      var local = lsGet(ENC_KEY, {});
      var voted = local.weekId === wid && !!local.voted;
      if (ONLINE) {
        return rpc('encuesta_resultados', { p_week: wid }).then(function (rows) {
          var votos = {};
          (rows || []).forEach(function (r) { votos[r.opcion] = r.n; });
          return { opciones: votos, voted: voted };
        });
      }
      // offline: baseline para no verse vacío + votos locales
      var base = { pomaire: 47, centro: 39, empate: 14 };
      var v = (local.weekId === wid && local.votes) ? local.votes : {};
      var opciones = {
        pomaire: (v.pomaire || 0) + base.pomaire,
        centro:  (v.centro  || 0) + base.centro,
        empate:  (v.empate  || 0) + base.empate
      };
      return Promise.resolve({ opciones: opciones, voted: voted });
    },
    votar: function (wid, opcion) {
      // marca localmente para evitar doble voto en este navegador
      var local = lsGet(ENC_KEY, {});
      if (local.weekId !== wid) local = { weekId: wid, votes: {}, voted: false };
      local.votes[opcion] = (local.votes[opcion] || 0) + 1;
      local.voted = true;
      lsSet(ENC_KEY, local);
      if (ONLINE) {
        return sb('/encuesta_votos', { method: 'POST', body: JSON.stringify({ week_id: wid, opcion: opcion }) });
      }
      return Promise.resolve();
    }
  };

  /* ════════ VISITAS ════════ */
  var VIS_KEY = 'hm_visitas_v2';
  var visitas = {
    /* Devuelve {total, hoy}. Cuenta 1 visita por navegador cada 30 min. */
    registrar: function () {
      var st = lsGet(VIS_KEY, { total: 2847, hoy: 0, ultima: 0, dia: '' });
      var ahora = Date.now();
      var nuevoVisit = (ahora - (st.ultima || 0)) > 30 * 60 * 1000;
      if (ONLINE) {
        return rpc('registrar_visita', { p_contar: nuevoVisit }).then(function (rows) {
          if (nuevoVisit) { st.ultima = ahora; lsSet(VIS_KEY, st); }
          var row = Array.isArray(rows) ? rows[0] : rows;
          return { total: (row && row.total) || 0, hoy: (row && row.hoy) || 0 };
        });
      }
      // offline
      var hoyStr = new Date().toDateString();
      if (st.dia !== hoyStr) { st.dia = hoyStr; st.hoy = 0; }
      if (nuevoVisit) { st.total = (st.total || 0) + 1; st.hoy = (st.hoy || 0) + 1; st.ultima = ahora; }
      lsSet(VIS_KEY, st);
      return Promise.resolve({ total: st.total, hoy: st.hoy });
    }
  };

  /* ════════ CONTACTOS (avisos por mail/WhatsApp) ════════ */
  var CONT_KEY = 'hm_contactos_v1';
  var contactos = {
    add: function (canal, valor) {
      if (ONLINE) {
        return sb('/contactos', { method: 'POST', body: JSON.stringify({ canal: canal, valor: valor }) });
      }
      var arr = lsGet(CONT_KEY, []);
      arr.push({ canal: canal, valor: valor, ts: Date.now() });
      lsSet(CONT_KEY, arr);
      return Promise.resolve();
    }
  };

  /* ════════ PUSH ════════ */
  function urlB64ToUint8(base64) {
    var padding = '='.repeat((4 - base64.length % 4) % 4);
    var b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(b64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  var push = {
    disponible: function () {
      return ('serviceWorker' in navigator) && ('PushManager' in window) &&
             ONLINE && !!(cfg.VAPID_PUBLIC_KEY);
    },
    /* Se suscribe al push y guarda la suscripción en Supabase. */
    suscribir: function () {
      if (!push.disponible()) return Promise.reject(new Error('push-no-config'));
      return navigator.serviceWorker.ready.then(function (reg) {
        return reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlB64ToUint8(cfg.VAPID_PUBLIC_KEY)
        });
      }).then(function (sub) {
        var j = sub.toJSON();
        return sb('/push_subs', {
          method: 'POST',
          headers: { 'Prefer': 'resolution=merge-duplicates' },
          body: JSON.stringify({
            endpoint: sub.endpoint,
            p256dh: j.keys.p256dh,
            auth: j.keys.auth
          })
        });
      });
    }
  };

  window.HM = {
    online: ONLINE,
    config: cfg,
    reportes: reportes,
    encuesta: encuesta,
    visitas: visitas,
    contactos: contactos,
    push: push
  };

  /* Cablea los enlaces de redes sociales del footer en CUALQUIER página.
     Usa las clases fs-ig / fs-tt / fs-wa. Si un enlace no está configurado,
     oculta ese botón (mejor eso que un link muerto). */
  function aplicarRedes() {
    var S = cfg.SOCIAL || {};
    function set(sel, url) {
      document.querySelectorAll(sel).forEach(function (el) {
        if (url) { el.href = url; } else { el.style.display = 'none'; }
      });
    }
    set('.fs-ig', S.instagram);
    set('.fs-tt', S.tiktok);
    set('.fs-wa', S.whatsappCanal);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', aplicarRedes);
  } else {
    aplicarRedes();
  }

  /* Registrar el Service Worker (habilita PWA offline, install prompt y push).
     Antes no se registraba en ninguna página: por eso no funcionaba nada de eso. */
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js').catch(function () {});
    });
  }
})();
