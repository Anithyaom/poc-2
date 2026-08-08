import { PlanWorkspace } from '@/components/PlanWorkspace';
import { Breadcrumb } from '@/components/ui';
import { apiGet } from '@/lib/api';
import type { Lab } from '@/lib/types';

// A regenerated plan must never render stale — see spec §10, caching discipline.
export const dynamic = 'force-dynamic';

export default async function PlanPage({ params, searchParams }: PageProps<'/labs/[id]/plan'>) {
  const { id } = await params;
  const { job } = await searchParams;

  const lab = await apiGet<Lab>(`/api/labs/${id}`);
  const initialJobId = typeof job === 'string' ? job : null;

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <Breadcrumb
        items={[
          { label: 'Courses', href: '/' },
          { label: lab.course_title, href: `/courses/${lab.course_id}` },
          { label: 'Simulation blueprint' },
        ]}
      />
      <PlanWorkspace lab={lab} initialJobId={initialJobId} />
    </main>
  );
}
