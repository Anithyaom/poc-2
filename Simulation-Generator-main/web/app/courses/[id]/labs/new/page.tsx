'use client';

import { useRouter } from 'next/navigation';
import { use, useEffect, useState } from 'react';
import { Breadcrumb } from '@/components/ui';
import type { Lab, TextbookOutline } from '@/lib/types';

const AUDIENCES = [
  'Grade 6',
  'Grade 7',
  'Grade 8',
  'Grade 9',
  'Grade 10',
  'Grade 11',
  'Grade 12',
  'Undergraduate',
  'Graduate',
];

const PLACEHOLDER =
  'I want students to see why a heavier ball and a lighter ball fall at the same ' +
  'rate, and what changes when there\'s air resistance.';

const MIN_CHARS = 20;

export default function NewLabPage({ params }: PageProps<'/courses/[id]/labs/new'>) {
  const { id: courseId } = use(params);
  const router = useRouter();

  const [description, setDescription] = useState('');
  const [audience, setAudience] = useState('Grade 9');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [books, setBooks] = useState<TextbookOutline[]>([]);
  const [sourceRef, setSourceRef] = useState('');

  // The picker is optional and only appears once the textbook has been extracted and
  // mounted; a failed or empty fetch just leaves it hidden.
  useEffect(() => {
    let live = true;
    fetch('/api/textbooks')
      .then((res) => (res.ok ? res.json() : []))
      .then((data: TextbookOutline[]) => {
        if (live) setBooks(data);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  const pickSource = (ref: string) => {
    setSourceRef(ref);
    // A section belongs to one grade's book; default the year group to match.
    const book = books.find((b) => b.chapters.some((c) => c.sections.some((s) => s.ref === ref)));
    if (book) setAudience(`Grade ${book.grade}`);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);

    const created = await fetch(`/api/courses/${courseId}/labs`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ description, audience, source_ref: sourceRef || null }),
    });
    if (!created.ok) {
      setBusy(false);
      setError(`Could not create the lab (${created.status})`);
      return;
    }
    const lab: Lab = await created.json();

    // Kick off LLM call #1 straight away, then hand the job id to the review
    // screen so it can poll rather than re-deriving it.
    const started = await fetch(`/api/labs/${lab.id}/plan:generate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: '{}',
    });
    if (!started.ok) {
      setBusy(false);
      setError(`Lab created, but the blueprint job did not start (${started.status})`);
      return;
    }
    const { job_id } = await started.json();
    router.push(`/labs/${lab.id}/plan?job=${job_id}`);
  };

  const tooShort = description.trim().length < MIN_CHARS;

  return (
    <main className="mx-auto w-full max-w-2xl px-6 py-10">
      <Breadcrumb
        items={[
          { label: 'Courses', href: '/' },
          { label: 'Course', href: `/courses/${courseId}` },
          { label: 'New lab' },
        ]}
      />

      <h1 className="mt-4 text-xl font-semibold tracking-tight">Describe the lab you want</h1>
      <p className="mt-1 text-sm text-neutral-400">
        Write it in your own words. The subject and topic get worked out for you — you
        confirm them when you review the simulation blueprint.
      </p>

      <form onSubmit={submit} className="mt-6 flex flex-col gap-5">
        <label className="flex flex-col gap-2">
          <span className="text-xs text-neutral-400">What should students come away with?</span>
          <textarea
            autoFocus
            rows={6}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={PLACEHOLDER}
            className="resize-none rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm leading-relaxed outline-none focus:border-sky-500"
          />
        </label>

        <label className="flex flex-col gap-2">
          <span className="text-xs text-neutral-400">Year group</span>
          <select
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            className="w-40 rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm"
          >
            {AUDIENCES.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>

        {books.length > 0 && (
          <label className="flex flex-col gap-2">
            <span className="text-xs text-neutral-400">Textbook section (optional)</span>
            <select
              value={sourceRef}
              onChange={(e) => pickSource(e.target.value)}
              className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm"
            >
              <option value="">None — work from my description only</option>
              {books.map((book) =>
                book.chapters.map((ch) => (
                  <optgroup
                    key={`${book.id}-${ch.part}-${ch.chapter}`}
                    label={`${book.title} ${book.grade} · Part ${ch.part} · Ch. ${ch.chapter} ${ch.title}`}
                  >
                    {ch.sections.map((s) => (
                      <option key={s.ref} value={s.ref}>
                        {s.number} {s.title} (pp. {s.page_start}–{s.page_end})
                      </option>
                    ))}
                  </optgroup>
                )),
              )}
            </select>
            <span className="text-xs text-neutral-500">
              The blueprint will follow this section&apos;s examples and language.
            </span>
          </label>
        )}

        {error && <p className="text-xs text-red-400">{error}</p>}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={busy || tooShort}
            className="rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-40"
          >
            {busy ? 'Starting…' : 'Draft simulation blueprint'}
          </button>
          {tooShort && description.length > 0 && (
            <span className="text-xs text-neutral-500">
              A little more detail — {MIN_CHARS - description.trim().length} characters to go.
            </span>
          )}
        </div>
      </form>
    </main>
  );
}
