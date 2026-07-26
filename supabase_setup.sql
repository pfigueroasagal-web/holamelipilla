-- ════════════════════════════════════════════════════════════════════════
--  supabase_setup.sql — Hola Melipilla
--  Cópialo COMPLETO y pégalo en Supabase → SQL Editor → RUN (una sola vez).
--  Crea las tablas, las políticas de seguridad (RLS) y las funciones que
--  usa el sitio para reportes, encuesta, visitas, contactos y push.
-- ════════════════════════════════════════════════════════════════════════

-- ─── 1) REPORTES VECINALES ───────────────────────────────────────────────
create table if not exists public.reportes (
  id          uuid primary key default gen_random_uuid(),
  tipo        text not null,
  sector      text,
  texto       text not null check (char_length(texto) <= 200),
  confirm     int  not null default 0,
  deny        int  not null default 0,
  created_at  timestamptz not null default now()
);
create index if not exists reportes_created_idx on public.reportes (created_at desc);

-- ─── 2) ENCUESTA (un registro por voto) ──────────────────────────────────
create table if not exists public.encuesta_votos (
  id          uuid primary key default gen_random_uuid(),
  week_id     text not null,
  opcion      text not null,
  created_at  timestamptz not null default now()
);
create index if not exists encuesta_week_idx on public.encuesta_votos (week_id);

-- ─── 3) VISITAS (contador único fila id=1) ───────────────────────────────
create table if not exists public.visitas (
  id          int primary key default 1,
  total       bigint not null default 0
);
insert into public.visitas (id, total) values (1, 0)
  on conflict (id) do nothing;

-- Log liviano de visitas para calcular "hoy" (se limpia solo a 3 días)
create table if not exists public.visitas_log (
  id          bigserial primary key,
  created_at  timestamptz not null default now()
);
create index if not exists visitas_log_idx on public.visitas_log (created_at);

-- ─── 4) CONTACTOS (avisos por mail / WhatsApp) ───────────────────────────
create table if not exists public.contactos (
  id          uuid primary key default gen_random_uuid(),
  canal       text not null,           -- 'email' | 'whatsapp'
  valor       text not null,
  created_at  timestamptz not null default now()
);

-- ─── 5) SUSCRIPCIONES PUSH ───────────────────────────────────────────────
create table if not exists public.push_subs (
  id          uuid primary key default gen_random_uuid(),
  endpoint    text unique not null,
  p256dh      text not null,
  auth        text not null,
  created_at  timestamptz not null default now()
);


-- ════════════════════════════════════════════════════════════════════════
--  FUNCIONES (RPC) — con SECURITY DEFINER para operaciones controladas
-- ════════════════════════════════════════════════════════════════════════

-- Reacción a un reporte (👍 confirm / 👎 deny) de forma atómica
create or replace function public.incrementar_reaccion(p_id uuid, p_campo text)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if p_campo = 'confirm' then
    update public.reportes set confirm = confirm + 1 where id = p_id;
  elsif p_campo = 'deny' then
    update public.reportes set deny = deny + 1 where id = p_id;
  end if;
end; $$;

-- Resultados agregados de la encuesta de una semana
create or replace function public.encuesta_resultados(p_week text)
returns table(opcion text, n bigint)
language sql security definer set search_path = public as $$
  select opcion, count(*)::bigint as n
  from public.encuesta_votos
  where week_id = p_week
  group by opcion;
$$;

-- Registra una visita (si p_contar) y devuelve total + visitas de hoy
create or replace function public.registrar_visita(p_contar boolean default true)
returns table(total bigint, hoy bigint)
language plpgsql security definer set search_path = public as $$
begin
  if p_contar then
    update public.visitas set total = total + 1 where id = 1;
    insert into public.visitas_log default values;
    -- limpieza oportunista de registros viejos
    delete from public.visitas_log where created_at < now() - interval '3 days';
  end if;
  return query
    select v.total,
           (select count(*)::bigint from public.visitas_log
             where created_at >= (now() at time zone 'America/Santiago')::date)
    from public.visitas v where v.id = 1;
end; $$;


-- ════════════════════════════════════════════════════════════════════════
--  SEGURIDAD (RLS) — la clave "anon" es pública, así que limitamos qué puede
--  hacer: leer lo público e insertar, pero nunca modificar/borrar a mano.
-- ════════════════════════════════════════════════════════════════════════
alter table public.reportes       enable row level security;
alter table public.encuesta_votos enable row level security;
alter table public.visitas        enable row level security;
alter table public.contactos      enable row level security;
alter table public.push_subs      enable row level security;

-- Reportes: cualquiera lee, cualquiera inserta (reacciones van por RPC)
drop policy if exists rep_sel on public.reportes;
create policy rep_sel on public.reportes for select using (true);
drop policy if exists rep_ins on public.reportes;
create policy rep_ins on public.reportes for insert with check (
  char_length(texto) between 1 and 200
);

-- Encuesta: nadie lee filas crudas (resultados van por RPC), todos insertan
drop policy if exists enc_ins on public.encuesta_votos;
create policy enc_ins on public.encuesta_votos for insert with check (true);

-- Visitas: sin acceso directo (todo pasa por la función registrar_visita)

-- Contactos: solo insertar (nadie puede leer la lista con la clave anon)
drop policy if exists cont_ins on public.contactos;
create policy cont_ins on public.contactos for insert with check (
  char_length(valor) between 3 and 200
);

-- Push subs: solo insertar / upsert
drop policy if exists push_ins on public.push_subs;
create policy push_ins on public.push_subs for insert with check (true);

-- ════════════════════════════════════════════════════════════════════════
--  LISTO. Ahora copia en config.js:
--    Project Settings → API → Project URL           → SUPABASE_URL
--    Project Settings → API → Project API keys: anon → SUPABASE_ANON_KEY
-- ════════════════════════════════════════════════════════════════════════
