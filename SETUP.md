# Activar las funciones de comunidad de Hola Melipilla

El sitio ya funciona sin configurar nada (usa almacenamiento local en el
navegador). Para activar la **comunidad real** (reportes, encuesta y visitas
compartidas entre todos los vecinos), las **redes sociales** y las
**notificaciones del turno**, sigue estos pasos. Toma ~15 minutos.

Todo lo que se configura se hace editando **`config.js`** (y unos secrets en
GitHub para el push). Nunca se rompe nada: si un valor queda vacío, esa
función simplemente cae al modo local o se oculta.

---

## 1) Backend gratis con Supabase (reportes, encuesta, visitas, contactos)

1. Crea una cuenta en <https://supabase.com> y un proyecto nuevo (plan **Free**).
2. En el proyecto, abre **SQL Editor** → **New query**.
3. Copia y pega **todo** el contenido de `supabase_setup.sql` y pulsa **Run**.
   Esto crea las tablas, las políticas de seguridad y las funciones.
4. Ve a **Project Settings → API** y copia:
   - **Project URL** → pégalo en `SUPABASE_URL`
   - **Project API keys → `anon` `public`** → pégalo en `SUPABASE_ANON_KEY`
5. Abre `config.js` y rellena esos dos valores:
   ```js
   SUPABASE_URL: 'https://TU-PROYECTO.supabase.co',
   SUPABASE_ANON_KEY: 'eyJhbGciOi...tu-clave-anon...',
   ```
6. Publica los cambios. Listo: ahora los reportes y la encuesta son
   compartidos por todos los vecinos en tiempo casi real.

> La clave `anon` es **pública a propósito** (va en el navegador). La seguridad
> la dan las políticas RLS del SQL: cualquiera puede leer los reportes e
> insertar, pero nadie puede leer la lista de contactos ni borrar datos ajenos.

---

## 2) Redes sociales

En `config.js`, sección `SOCIAL`, pon tus enlaces reales:

```js
SOCIAL: {
  instagram:     'https://www.instagram.com/TU_CUENTA',
  tiktok:        'https://www.tiktok.com/@TU_CUENTA',
  whatsappCanal: 'https://whatsapp.com/channel/XXXXXXXX'  // Canal o comunidad
}
```

- Si dejas uno **vacío**, ese botón se **oculta** automáticamente (mejor que
  un enlace muerto).
- El `whatsappCanal` alimenta también el botón grande **"Unirme al Canal de
  WhatsApp"** de la portada. Para crear un Canal: WhatsApp → pestaña
  Novedades/Actualizaciones → **Crear canal**.

---

## 3) Notificaciones push del turno de farmacia

Esto avisa a los vecinos cada mañana qué farmacia está de turno.

### a) Generar las claves VAPID (una sola vez)

En tu computador (o en <https://web-push-codelab.glitch.me> para generarlas al
vuelo):

```bash
pip install pywebpush py-vapid
vapid --gen           # crea private_key.pem y public_key.pem
vapid --applicationServerKey   # imprime la clave pública en formato web
```

Obtendrás una **clave pública** (base64 url-safe, larga) y una **clave privada**.

### b) Configurar el frontend

En `config.js` pega **solo la pública**:

```js
VAPID_PUBLIC_KEY: 'BEl62iUY...tu-clave-publica...'
```

### c) Configurar el envío automático (GitHub Actions)

En tu repo de GitHub: **Settings → Secrets and variables → Actions → New
repository secret**, y crea estos secrets:

| Secret                 | Valor                                            |
|------------------------|--------------------------------------------------|
| `SUPABASE_URL`         | la misma URL del paso 1                          |
| `SUPABASE_SERVICE_KEY` | Supabase → API → clave **`service_role`** (secreta) |
| `VAPID_PUBLIC_KEY`     | la clave pública VAPID                            |
| `VAPID_PRIVATE_KEY`    | la clave privada VAPID                            |
| `VAPID_SUBJECT`        | `mailto:tu-correo@ejemplo.cl`                     |

El workflow `.github/workflows/push-diario.yml` ya está listo: corre todos los
días ~08:00 (Chile) y también puedes lanzarlo a mano desde la pestaña
**Actions → Aviso diario del turno de farmacia → Run workflow**.

> `service_role` es **secreta**: solo va en los secrets de GitHub, **nunca** en
> `config.js` ni en el repo.

---

## 4) Eventos especiales del fin de semana

Edita `eventos.json` para agregar panoramas puntuales (fiestas, ferias
costumbristas, eventos municipales). Se muestran destacados arriba de las
ferias fijas, solo durante la semana de su fecha. Borra los que ya pasaron.

---

## ¿Qué pasa si no configuro nada?

- **Reportes / encuesta / visitas** → funcionan en modo local (por navegador).
- **Redes sociales** → los botones sin enlace se ocultan.
- **Push** → el botón "Avísame del turno" muestra un aviso local amable.
- **Eventos** → se muestran solo las ferias cíclicas.

Nada del sitio se rompe en ningún caso.
