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
      {lab.source && (
        <p className="mt-3 text-xs text-neutral-500">
          Textbook source:{' '}
          <span className="text-neutral-300">
            {lab.source.book} {lab.source.grade}, Part {lab.source.part}, Ch. {lab.source.chapter}{' '}
            {lab.source.chapter_title} — §{lab.source.number} {lab.source.title} (pp.{' '}
            {lab.source.page_start}–{lab.source.page_end})
          </span>
        </p>
      )}
      <PlanWorkspace lab={lab} initialJobId={initialJobId} />
    </main>
  );
}
