/**
 * Demo-workspace session helpers.
 *
 * - Server side: read/write the `demo_session` httpOnly cookie via Next.js
 *   `cookies()` (async in Next.js 15+).
 * - Client side: the page bootstraps the session via `getOrInitDemoSession()`
 *   (server action), stores the returned id in React state, and forwards it
 *   as `X-Session-Id` on every direct fetch to the FastAPI gateway.
 */

import { cookies } from "next/headers";

export const DEMO_COOKIE = "demo_session";
export const GLOBAL_TENANT = "global";

export function isDemoMode(): boolean {
  // Server actions see DEMO_MODE; client components see NEXT_PUBLIC_DEMO_MODE.
  // We probe both so this helper works in either context.
  const v =
    process.env.DEMO_MODE ?? process.env.NEXT_PUBLIC_DEMO_MODE ?? "false";
  return v.trim().toLowerCase() === "true";
}

// Server actions accept either NEXT_PUBLIC_API_URL (single var for cloud
// deploys) or API_GATEWAY_URL (legacy/local). The first wins.
const API_GATEWAY_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.API_GATEWAY_URL ??
  "http://localhost:8000"
).replace(/\/$/, "");

export type DemoInvoiceSummary = {
  invoice_id: string;
  vendor: string;
  pdf_total: number;
  expected_total: number;
  expected_status: "MATCH" | "DISCREPANCY";
};

export type DemoSession = {
  session_id: string;
  ttl_seconds: number;
  invoices: DemoInvoiceSummary[];
};

/** Read the demo session_id from the httpOnly cookie (server-only). */
export async function readDemoSessionId(): Promise<string | null> {
  const jar = await cookies();
  const v = jar.get(DEMO_COOKIE)?.value;
  return v && v.startsWith("demo_") ? v : null;
}

/**
 * Server-action helper: returns the active demo session, minting a new one
 * via POST /demo/init if no cookie is set. Idempotent for repeat callers.
 *
 * Throws when DEMO_MODE is off — UI should not call this in local dev.
 */
export async function getOrInitDemoSession(): Promise<DemoSession> {
  if (!isDemoMode()) {
    throw new Error("getOrInitDemoSession called with DEMO_MODE off");
  }

  const existing = await readDemoSessionId();
  if (existing) {
    const res = await fetch(`${API_GATEWAY_URL}/demo/session`, {
      headers: { "X-Session-Id": existing },
      cache: "no-store",
    });
    if (res.ok) {
      return (await res.json()) as DemoSession;
    }
    // Cookie present but backend rejected → cookie is stale; mint new.
  }

  const initRes = await fetch(`${API_GATEWAY_URL}/demo/init`, {
    method: "POST",
    cache: "no-store",
  });
  if (!initRes.ok) {
    throw new Error(`Demo init failed: HTTP ${initRes.status}`);
  }
  const session = (await initRes.json()) as DemoSession;

  const jar = await cookies();
  jar.set(DEMO_COOKIE, session.session_id, {
    httpOnly: true,
    sameSite: "lax",
    maxAge: session.ttl_seconds,
    path: "/",
  });
  return session;
}

/**
 * Clears the demo cookie and POSTs /demo/init so the UI gets a fresh session
 * id and newly seeded invoice PDFs (after a batch moved prior files away).
 */
export async function mintFreshDemoSession(): Promise<DemoSession> {
  if (!isDemoMode()) {
    throw new Error("mintFreshDemoSession called with DEMO_MODE off");
  }

  const jar = await cookies();
  // Next.js 16+: delete accepts a single cookie descriptor (name + path).
  jar.delete({ name: DEMO_COOKIE, path: "/" });

  const initRes = await fetch(`${API_GATEWAY_URL}/demo/init`, {
    method: "POST",
    cache: "no-store",
  });
  if (!initRes.ok) {
    throw new Error(`Demo init failed: HTTP ${initRes.status}`);
  }
  const session = (await initRes.json()) as DemoSession;

  jar.set(DEMO_COOKIE, session.session_id, {
    httpOnly: true,
    sameSite: "lax",
    maxAge: session.ttl_seconds,
    path: "/",
  });
  return session;
}

/** Tenant id for Prisma scoping. ``"global"`` outside demo mode. */
export async function currentTenantId(): Promise<string> {
  if (!isDemoMode()) return GLOBAL_TENANT;
  return (await readDemoSessionId()) ?? GLOBAL_TENANT;
}
