'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { PlanEditor } from '@/components/PlanEditor';
import { useJob } from '@/lib/useJob';
import type { Lab, Plan } from '@/lib/types';

interface Props {
  lab: Lab;
  initialJobId: string | null;
}

function isSimulationBlueprint(value: Plan | null): value is Plan {
  return value !== null && 'simulation_experience' in value && 'controls' in value;
}

/**
 * The plan review gate.
 *
 * This screen is load-bearing: the plan owns the manifest (spec §6.1), so what the
 * teacher accepts here — including every slider range — is exactly what the
 * simulation gets built from. Editing a range here is the human check on the
 * model's physics, and it costs no LLM call.
 */
export function PlanWorkspace({ lab, initialJobId }: Props) {
  const router = useRouter();
  const [jobId, setJobId] = useState<string | null>(initialJobId);
  const serverDraft = isSimulationBlueprint(lab.latest_plan_json) ? lab.latest_plan_json : null;
  const [sourcePlanId, setSourcePlanId] = useState(lab.latest_plan_id);
  const [draft, setDraft] = useState<Plan | null>(serverDraft);
  const [description, setDescription] = useState(lab.description);
  const [asking, setAsking] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const job = useJob(jobId);
  const generating = !!jobId && (!job || job.status === 'queued' || job.status === 'running');

  // Adjust local editing state when a server refresh supplies a new version.
  if (sourcePlanId !== lab.latest_plan_id) {
    setSourcePlanId(lab.latest_plan_id);
    setDraft(serverDraft);
    setDescription(lab.description);
  }

  const refreshedJob = useRef<string | null>(null);
  // Let the Server Component re-fetch rather than duplicating fetch logic here.
  // A finished simulation is the one job that leaves this screen — the teacher
  // asked for a simulation, so land them on it rather than back on the blueprint.
  useEffect(() => {
    if (jobId && job?.status === 'succeeded' && refreshedJob.current !== jobId) {
      refreshedJob.current = jobId;
      if (job.job_type === 'generate_simulation') router.push(`/labs/${lab.id}/sim`);
      else router.refresh();
    }
  }, [job?.status, job?.job_type, jobId, lab.id, router]);

  const post = async (path: string, body: unknown) => {
    setBusy(true);
    setError(null);
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    setBusy(false);
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      setError(detail?.detail ? JSON.stringify(detail.detail) : `Request failed (${res.status})`);
      return null;
    }
    return res.json();
  };

  const regenerate = async () => {
    const data = await post(`/api/labs/${lab.id}/plan:generate`, { description });
    if (data) setJobId(data.job_id);
  };

  // Accepting a blueprint IS asking for the simulation — there is nothing else a
  // teacher would do next, so the generation starts here rather than behind a
  // second button they have to find.
  const buildSimulation = async () => {
    const data = await post(`/api/labs/${lab.id}/simulations:generate`, {});
    if (data) setJobId(data.job_id);
  };

  const decide = async (decision: 'accept' | 'accept_with_modifications' | 'reject') => {
    const body =
      decision === 'accept_with_modifications' ? { decision, edits: draft } : { decision };
    const data = await post(`/api/plans/${lab.latest_plan_id}/decision`, body);
    if (!data) return;
    if (decision === 'reject') router.refresh();
    else await buildSimulation();
  };

  const edited = draft !== null && JSON.stringify(draft) !== JSON.stringify(lab.latest_plan_json);

  // Unsaved section edits ride along: the route persists them as their own pending
  // version before the model runs, so a failed revision cannot lose them.
  const requestChanges = async () => {
    const data = await post(`/api/plans/${lab.latest_plan_id}/revisions`, {
      feedback_text: feedback,
      ...(edited ? { edits: draft } : {}),
    });
    if (data) {
      setFeedback('');
      setAsking(false);
      setJobId(data.job_id);
    }
  };

  if (generating) {
    return (
      <section className="mt-16 flex flex-col items-center gap-3 text-center">
        <div className="h-1 w-40 overflow-hidden rounded bg-neutral-800">
          <div className="h-full w-1/3 animate-pulse rounded bg-sky-400" />
        </div>
        <p className="text-sm text-neutral-300">
          {job?.status !== 'running'
            ? 'Queued…'
            : job.job_type === 'generate_simulation'
              ? 'Building the simulation…'
              : job.job_type === 'revise_plan'
                ? 'Revising the simulation blueprint…'
                : 'Drafting the simulation blueprint…'}
        </p>
        <p className="max-w-sm text-xs text-neutral-500">
          {job?.job_type === 'generate_simulation'
            ? 'This takes a couple of minutes. We are writing the simulation from the blueprint you approved, then checking it drives every control you signed off.'
            : job?.job_type === 'revise_plan'
              ? 'This takes a minute or two. We are applying your changes and keeping everything you did not mention.'
              : 'This takes a minute or two. We are turning your request into controls, visuals, behavior rules, and expected outcomes for you to review.'}
        </p>
      </section>
    );
  }

  if (job?.status === 'failed') {
    const building = job.job_type === 'generate_simulation';
    return (
      <section className="mt-10 flex flex-col gap-4">
        <div className="rounded-lg border border-red-900/60 bg-red-950/30 p-4">
          <p className="text-sm text-red-300">
            {building
              ? 'The simulation could not be built from this blueprint.'
              : 'The simulation blueprint could not be drafted.'}
          </p>
          <p className="mt-1 whitespace-pre-line font-mono text-xs text-red-400/80">{job.error}</p>
        </div>
        <button
          type="button"
          onClick={building ? buildSimulation : regenerate}
          disabled={busy}
          className="self-start rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-40"
        >
          Try again
        </button>
      </section>
    );
  }

  // Rejected, missing, or stored in the retired lesson-plan format: return to prose.
  if (!draft || lab.latest_plan_decision === 'rejected') {
    return (
      <section className="mt-6 flex flex-col gap-4">
        {lab.latest_plan_decision === 'rejected' && (
          <p className="text-sm text-neutral-400">
            Blueprint v{lab.latest_plan_version} was rejected. Adjust the description and
            draft another — the rejected version is kept.
          </p>
        )}
        {!draft && lab.latest_plan_json && lab.latest_plan_decision !== 'rejected' && (
          <div className="rounded-xl border border-amber-900/60 bg-amber-950/20 p-4">
            <p className="text-sm font-medium text-amber-200">This draft uses the retired lesson-plan format.</p>
            <p className="mt-1 text-xs leading-relaxed text-amber-200/60">
              Generate a new version to review it as a focused simulation blueprint. The old version remains in history.
            </p>
          </div>
        )}
        <textarea
          rows={6}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="resize-none rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm leading-relaxed outline-none focus:border-sky-500"
        />
        {error && <p className="text-xs text-red-400">{error}</p>}
        <button
          type="button"
          onClick={regenerate}
          disabled={busy || description.trim().length < 20}
          className="self-start rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-40"
        >
          {busy ? 'Starting…' : 'Draft simulation blueprint'}
        </button>
      </section>
    );
  }

  const accepted = lab.latest_plan_decision === 'accepted';

  return (
    <section className="mt-6 flex flex-col gap-6">
      {accepted && (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-emerald-900/60 bg-emerald-950/20 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm text-emerald-300">
              Simulation blueprint v{lab.latest_plan_version} accepted.
            </p>
            <p className="mt-1 text-xs text-emerald-400/70">
              {lab.current_simulation_id
                ? 'The simulation was built from this blueprint. Its controls and displayed values are exactly the ones reviewed here.'
                : 'This approved blueprint is what the simulation gets built from. Its controls and displayed values will carry through exactly as reviewed.'}
            </p>
          </div>
          {lab.current_simulation_id ? (
            <Link
              href={`/labs/${lab.id}/sim`}
              className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950"
            >
              Open the simulation
            </Link>
          ) : (
            <button
              type="button"
              onClick={buildSimulation}
              disabled={busy}
              className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-40"
            >
              {busy ? 'Starting…' : 'Build the simulation'}
            </button>
          )}
        </div>
      )}

      <PlanEditor plan={draft} onChange={setDraft} readOnly={accepted} />

      {!accepted && (
        <>
          {error && <p className="text-xs text-red-400">{error}</p>}

          {asking && (
            <div className="rounded-xl border border-sky-900/60 bg-sky-950/20 p-4">
              <label className="block">
                <span className="mb-2 block text-[11px] font-medium uppercase tracking-wide text-sky-300/80">
                  What should change?
                </span>
                <textarea
                  autoFocus
                  rows={4}
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="The list size should be a dropdown of powers of two, not a slider — 8 up to 128."
                  className="w-full resize-y rounded-lg border border-neutral-800 bg-neutral-950/70 px-3 py-2 text-sm leading-relaxed text-neutral-200 outline-none transition focus:border-sky-700"
                />
              </label>
              <p className="mt-2 text-xs text-neutral-500">
                Everything you don&apos;t mention stays as it is.
              </p>
              {edited && (
                <p className="mt-2 text-xs text-emerald-300/80">
                  Your unsaved edits will be kept and revised together with this request.
                </p>
              )}
              <button
                type="button"
                disabled={busy || feedback.trim().length < 4}
                onClick={requestChanges}
                className="mt-3 rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-40"
              >
                {busy ? 'Starting…' : 'Revise blueprint'}
              </button>
            </div>
          )}

          <div className="sticky bottom-0 flex flex-wrap items-center gap-3 border-t border-neutral-800 bg-neutral-950/95 py-4 backdrop-blur">
            <button
              type="button"
              disabled={busy}
              onClick={() => decide(edited ? 'accept_with_modifications' : 'accept')}
              className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-40"
            >
              {edited ? 'Accept with my changes' : 'Accept blueprint'}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setAsking(!asking)}
              className="rounded-md border border-sky-800 px-4 py-2 text-sm text-sky-300 transition hover:bg-sky-950/30 disabled:opacity-40"
            >
              {asking ? 'Cancel' : 'Request changes'}
            </button>
            {edited && !asking && (
              <span className="text-xs text-neutral-500">
                Your edits are saved as a new version — the drafted one is kept.
              </span>
            )}
            {/* Subordinate to Request changes, but still plainly a button: redrafting
                discards this blueprint and starts again from the original description,
                so it must be findable and unambiguous — not camouflaged. */}
            <button
              type="button"
              disabled={busy}
              onClick={() => decide('reject')}
              className="ml-auto rounded-md border border-neutral-700 px-4 py-2 text-sm text-neutral-400 transition hover:border-neutral-500 hover:text-neutral-200 disabled:opacity-40"
            >
              Reject and start over
            </button>
          </div>
        </>
      )}
    </section>
  );
}
