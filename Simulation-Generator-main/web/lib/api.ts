import 'server-only';

/**
 * Server-side reads for Server Components.
 *
 * Generated artifacts change under the user's feet, so every read opts out of
 * Next's default fetch cache. A cached plan page after a regeneration is the most
 * likely "why didn't it update?" bug in this stack — pair this with
 * `export const dynamic = 'force-dynamic'` on any route that reads one.
 */

const BACKEND = process.env.BACKEND_URL!;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND}${path}`, { cache: 'no-store' });
  } catch {
    throw new ApiError(502, `Backend unreachable at ${BACKEND}. Is \`docker compose up\` running?`);
  }
  if (!res.ok) {
    throw new ApiError(res.status, `GET ${path} failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}
