import Link from 'next/link';
import { SimWorkspace } from '@/components/SimWorkspace';
import { apiGet } from '@/lib/api';
import type { Lab, Plan, PlanVersion, Simulation } from '@/lib/types';

// A freshly generated simulation must never render stale — see spec §10.
export const dynamic = 'force-dynamic';

export default async function SimPage({ params }: PageProps<'/labs/[id]/sim'>) {
  const { id } = await params;
  const lab = await apiGet<Lab>(`/api/labs/${id}`);

  if (!lab.current_simulation_id) {
    return (
      <main className="mx-auto w-full max-w-2xl px-6 py-20 text-center">
        <p className="text-sm text-neutral-300">This lab has no simulation yet.</p>
        <p className="mt-2 text-xs text-neutral-500">
          A simulation is built from an accepted blueprint.
        </p>
        <Link
          href={`/labs/${id}/plan`}
          className="mt-6 inline-block rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-neutral-950"
        >
          Go to the blueprint
        </Link>
      </main>
    );
  }

  // The blueprint the core was built from, not the newest one: a revision after
  // generation must not silently re-caption a simulation it did not produce.
  const [simulation, accepted] = await Promise.all([
    apiGet<Simulation>(`/api/simulations/${lab.current_simulation_id}`),
    lab.active_plan_id
      ? apiGet<PlanVersion>(`/api/plans/${lab.active_plan_id}`).catch(() => null)
      : Promise.resolve(null),
  ]);

  const plan = (accepted?.plan_json as Plan | undefined) ?? null;

  return (
    <main className="flex h-dvh flex-col bg-neutral-950 text-neutral-100">
      <header className="flex shrink-0 items-center gap-3 border-b border-neutral-800 px-5 py-3 text-xs">
        <Link href={`/courses/${lab.course_id}`} className="text-neutral-500 hover:text-neutral-300">
          {lab.course_title}
        </Link>
        <span aria-hidden className="text-neutral-700">
          /
        </span>
        <h1 className="font-medium text-neutral-200">{simulation.manifest_json.title}</h1>
        <span className="rounded bg-neutral-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-neutral-400">
          v{simulation.version}
        </span>
        <Link
          href={`/labs/${id}/plan`}
          className="ml-auto text-neutral-500 hover:text-neutral-300"
        >
          View blueprint
        </Link>
      </header>

      <SimWorkspace simulation={simulation} plan={plan} />
    </main>
  );
}
