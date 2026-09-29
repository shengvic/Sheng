import { NextResponse, type NextRequest } from "next/server";

import { checkCsrf } from "@/lib/csrf";
import { SESSION_COOKIE, apiUrl } from "@/lib/server/config";

// Backend-for-frontend proxy: the browser calls /api/* with its httpOnly session cookie; this
// handler adds the bearer token server-side (ADR-018). Only these headers cross in each way.
const FORWARD_REQUEST = ["accept", "content-type", "user-agent"];
const FORWARD_RESPONSE = ["content-type", "content-disposition", "cache-control"];

async function handle(request: NextRequest): Promise<Response> {
  const bad = checkCsrf(request.method, request.headers, request.headers.get("host"));
  if (bad) return NextResponse.json({ detail: bad }, { status: 403 });
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "not signed in" }, { status: 401 });

  // Keep the raw (still percent-encoded) path so ids containing '/', '#' survive.
  const raw = new URL(request.url);
  const path = raw.pathname.replace(/^\/api/, "");
  if (!path.startsWith("/v1/")) return NextResponse.json({ detail: "not found" }, { status: 404 });

  const headers = new Headers({ authorization: `Bearer ${token}` });
  for (const h of FORWARD_REQUEST) {
    const v = request.headers.get(h);
    if (v) headers.set(h, v);
  }
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const upstream = await fetch(`${apiUrl()}${path}${raw.search}`, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
    redirect: "manual",
  }).catch(() => null);
  if (!upstream) return NextResponse.json({ detail: "API unavailable" }, { status: 502 });

  const out = new NextResponse(upstream.body, { status: upstream.status });
  for (const h of FORWARD_RESPONSE) {
    const v = upstream.headers.get(h);
    if (v) out.headers.set(h, v);
  }
  out.headers.set("cache-control", "no-store");
  if (upstream.status === 401) out.cookies.delete(SESSION_COOKIE);
  return out;
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
