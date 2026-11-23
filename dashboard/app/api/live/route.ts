// Live numbers endpoint. POST polls Twitch / Kick / YouTube / X and upserts `live_stats`; Supabase Realtime then
// pushes the change to every open dashboard. GET reports which sources have keys (never the keys themselves).
// Auth: the signed-in owner, or `Authorization: Bearer $CRON_SECRET` for a scheduler (pg_cron / Vercel cron).
import { createClient } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { IS_DEMO, SUPABASE_URL } from "@/lib/env";
import { pollAll, sourcesConfigured } from "@/lib/live/sources";
import { serverClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

const MIN_GAP_S = 30;          // never hit the platforms more than twice a minute, however many tabs are open
const SNAP_OWN_MIN = 60;       // own-channel history point once an hour
const SNAP_LIVE_MIN = 10;      // streamer viewer history point every 10 min while live

function isCron(req: NextRequest): boolean {
  const secret = process.env.CRON_SECRET;
  return !!secret && req.headers.get("authorization") === `Bearer ${secret}`;
}

async function allowed(req: NextRequest): Promise<boolean> {
  if (isCron(req)) return true;
  const sb = await serverClient();
  const { data } = await sb.rpc("is_owner");
  return data === true;
}

function admin() {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) return null;
  return createClient(SUPABASE_URL, key, { auth: { persistSession: false, autoRefreshToken: false } });
}

export async function GET(req: NextRequest) {
  if (IS_DEMO) return NextResponse.json({ demo: true, configured: sourcesConfigured(process.env) });
  if (isCron(req)) return POST(req);   // Vercel cron calls GET with the secret
  if (!(await allowed(req))) return NextResponse.json({ error: "not allowed" }, { status: 401 });
  return NextResponse.json({ configured: sourcesConfigured(process.env), writer: !!process.env.SUPABASE_SERVICE_ROLE_KEY });
}

export async function POST(req: NextRequest) {
  if (IS_DEMO) return NextResponse.json({ demo: true });
  if (!(await allowed(req))) return NextResponse.json({ error: "not allowed" }, { status: 401 });
  const db = admin();
  if (!db) return NextResponse.json({ error: "SUPABASE_SERVICE_ROLE_KEY not set on the server" }, { status: 503 });

  const force = req.nextUrl.searchParams.get("force") === "1";
  const { data: last, error: le } = await db.from("live_stats").select("updated_at").order("updated_at", { ascending: false }).limit(1);
  if (le) return NextResponse.json({ error: `live_stats: ${le.message}` }, { status: 500 });
  const age = last?.[0] ? (Date.now() - Date.parse(last[0].updated_at)) / 1000 : Infinity;
  if (!force && age < MIN_GAP_S) return NextResponse.json({ skipped: true, age_s: Math.round(age) });

  const { data: streamers, error: se } = await db.from("streamers").select("id,twitch_login,kick_slug,avatar_url");
  if (se) return NextResponse.json({ error: se.message }, { status: 500 });
  const { rows, errors } = await pollAll(streamers ?? [], process.env);
  const at = new Date().toISOString();
  if (rows.length) {
    const { error: ue } = await db.from("live_stats").upsert(rows.map((r) => ({ ...r, updated_at: at })), { onConflict: "key" });
    if (ue) errors.write = ue.message;
  }

  // Real profile pictures: copy the platform avatar onto the streamer when it changed.
  for (const s of streamers ?? []) {
    const r = rows.find((x) => x.avatar_url && (x.key === `twitch:${s.twitch_login?.toLowerCase()}` || x.key === `kick:${s.kick_slug?.toLowerCase()}`));
    if (r?.avatar_url && r.avatar_url !== s.avatar_url) await db.from("streamers").update({ avatar_url: r.avatar_url }).eq("id", s.id);
  }

  // History for the growth charts, one point per time bucket. The unique (key, metric, slot) index makes a
  // second poller in the same bucket a no-op, so two open dashboards never write a duplicate point.
  const now = Date.now();
  const points: { key: string; metric: string; value: number; at: string; slot: number }[] = [];
  for (const r of rows) {
    if (r.kind === "own") {
      const slot = Math.floor(now / (SNAP_OWN_MIN * 60_000));
      for (const m of ["followers", "views", "posts"] as const) if (r[m] != null) points.push({ key: r.key, metric: m, value: r[m]!, at, slot });
    }
    if (r.kind === "streamer" && r.is_live && r.viewers != null) {
      points.push({ key: r.key, metric: "viewers", value: r.viewers, at, slot: Math.floor(now / (SNAP_LIVE_MIN * 60_000)) });
    }
  }
  if (points.length) {
    const { error: pe } = await db.from("stat_snapshots").upsert(points, { onConflict: "key,metric,slot", ignoreDuplicates: true });
    if (pe) errors.snapshots = pe.message;
  }

  return NextResponse.json({ updated: rows.length, snapshots: points.length, errors });
}
