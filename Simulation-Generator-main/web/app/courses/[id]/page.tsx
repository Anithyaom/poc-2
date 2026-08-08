import Link from 'next/link';
import { Breadcrumb, EmptyState, PageHeader, StatusPill } from '@/components/ui';
import { apiGet } from '@/lib/api';
import type { CourseDetail } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function CoursePage({ params }: PageProps<'/courses/[id]'>) {
  const { id } = await params;
  const course = await apiGet<CourseDetail>(`/api/courses/${id}`);

  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-10">
      <Breadcrumb items={[{ label: 'Courses', href: '/' }, { label: course.title }]} />

      <div className="mt-4">
        <PageHeader title={course.title} subtitle={course.subject}>
          <Link
            href={`/courses/${id}/labs/new`}
            className="shrink-0 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-neutral-950"
          >
            New lab
          </Link>
        </PageHeader>
      </div>

      <div className="mt-6 flex flex-col gap-2">
        {course.labs.length === 0 ? (
          <EmptyState>
            No simulations yet. Describe one in your own words and a blueprint will be drafted for you.
          </EmptyState>
        ) : (
          course.labs.map((lab) => (
            <Link
              key={lab.id}
              href={`/labs/${lab.id}/plan`}
              className="flex items-center justify-between gap-4 rounded-lg border border-neutral-800 px-4 py-3 hover:border-neutral-700 hover:bg-neutral-900"
            >
              <span className="min-w-0 truncate text-sm">{lab.title}</span>
              <span className="flex shrink-0 items-center gap-3">
                <span className="text-xs text-neutral-500">{lab.audience}</span>
                <StatusPill status={lab.status} />
              </span>
            </Link>
          ))
        )}
      </div>
    </main>
  );
}
