'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

export function NewCourseForm() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const res = await fetch('/api/courses', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ title, subject }),
    });
    setBusy(false);
    if (!res.ok) {
      setError(`Could not create the course (${res.status})`);
      return;
    }
    setOpen(false);
    setTitle('');
    setSubject('');
    // Let the Server Component re-fetch rather than duplicating fetch logic here.
    router.refresh();
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="shrink-0 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-neutral-950"
      >
        New course
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="flex shrink-0 flex-col items-end gap-2">
      <input
        autoFocus
        required
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Grade 9 Physics"
        className="w-56 rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm outline-none focus:border-sky-500"
      />
      <input
        required
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Physics"
        className="w-56 rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm outline-none focus:border-sky-500"
      />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-400"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-sky-500 px-3 py-1.5 text-xs font-medium text-neutral-950 disabled:opacity-40"
        >
          {busy ? 'Creating…' : 'Create'}
        </button>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </form>
  );
}
