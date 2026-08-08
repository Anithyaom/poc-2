'use client';

import { useEffect, useState } from 'react';
import type { Job } from './types';

const POLL_MS = 1500;

/**
 * Polls /api/jobs/{id} until the status is terminal.
 *
 * Reads the `generation_jobs` row through the BFF — never Celery's result
 * backend. Pass `null` to idle.
 */
export function useJob(jobId: string | null) {
  const [state, setState] = useState<{ jobId: string | null; job: Job | null }>({
    jobId,
    job: null,
  });

  if (state.jobId !== jobId) {
    setState({ jobId, job: null });
  }

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`, { cache: 'no-store' });
        const data: Job = await res.json();
        if (cancelled) return;
        setState({ jobId, job: data });
        if (data.status === 'queued' || data.status === 'running') {
          timer = setTimeout(poll, POLL_MS);
        }
      } catch {
        if (!cancelled) timer = setTimeout(poll, POLL_MS);
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  return state.jobId === jobId ? state.job : null;
}
