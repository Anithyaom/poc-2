import Link from 'next/link';
import { NewCourseForm } from '@/components/NewCourseForm';
import { EmptyState, PageHeader } from '@/components/ui';
import { apiGet } from '@/lib/api';
import type { Course } from '@/lib/types';

// Generated artifacts change under the user's feet; never serve a cached page.
export const dynamic = 'force-dynamic';

export default async function CourseListPage() {
  const courses = await apiGet<Course[]>('/api/courses');

  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-10">
      <PageHeader title="Your courses" subtitle="A course is a folder of labs.">
        <NewCourseForm />
      </PageHeader>

      <div className="mt-6 flex flex-col gap-2">
        {courses.length === 0 ? (
          <EmptyState>No courses yet. Create one to get started.</EmptyState>
        ) : (
          courses.map((course) => (
            <Link
              key={course.id}
              href={`/courses/${course.id}`}
              className="flex items-center justify-between rounded-lg border border-neutral-800 px-4 py-3 hover:border-neutral-700 hover:bg-neutral-900"
            >
              <span className="text-sm font-medium">{course.title}</span>
              <span className="text-xs text-neutral-500">{course.subject}</span>
            </Link>
          ))
        )}
      </div>
    </main>
  );
}
