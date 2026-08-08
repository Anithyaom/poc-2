import type { NextRequest } from 'next/server';

// Catch-all BFF passthrough: the browser calls Next.js at /api/<path>, and this
// forwards verbatim to ${BACKEND_URL}/api/<path> (nginx → FastAPI). One URL
// vocabulary, no CORS surface, no backend address in the client bundle.
//
// Promote an individual route to a hand-written handler only when it needs to do
// something extra (response shaping, auth header injection, caching).

const BACKEND = process.env.BACKEND_URL!;

export const dynamic = 'force-dynamic';

async function proxy(request: NextRequest, ctx: RouteContext<'/api/[...path]'>) {
  const { path } = await ctx.params;
  // Path segments arrive decoded; re-encode all but ':' so `simulations:generate`
  // survives the round trip intact.
  const suffix = path.map((s) => encodeURIComponent(s).replace(/%3A/g, ':')).join('/');
  const target = `${BACKEND}/api/${suffix}${request.nextUrl.search}`;

  const init: RequestInit = {
    method: request.method,
    headers: { 'content-type': request.headers.get('content-type') ?? 'application/json' },
    cache: 'no-store',
  };
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.text();
  }

  try {
    const upstream = await fetch(target, init);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        'content-type': upstream.headers.get('content-type') ?? 'application/json',
      },
    });
  } catch {
    // The backend stack being down is the most common local failure; make it read
    // as a clear 502 rather than an opaque Next.js error page.
    return Response.json(
      { detail: `Backend unreachable at ${BACKEND}. Is \`docker compose up\` running?` },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
