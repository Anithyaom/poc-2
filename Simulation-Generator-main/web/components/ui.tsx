import Link from 'next/link';
import type { LabStatus } from '@/lib/types';

const STATUS_LABEL: Record<LabStatus, string> = {
  draft: 'Draft',
  plan_review: 'Blueprint ready to review',
  plan_accepted: 'Blueprint accepted',
  sim_ready: 'Simulation ready',
  refining: 'Refining',
};

const STATUS_TONE: Record<LabStatus, string> = {
  draft: 'bg-neutral-800 text-neutral-400',
  plan_review: 'bg-sky-500/15 text-sky-300',
  plan_accepted: 'bg-emerald-500/15 text-emerald-300',
  sim_ready: 'bg-emerald-500/15 text-emerald-300',
  refining: 'bg-amber-500/15 text-amber-300',
};

export function StatusPill({ status }: { status: LabStatus }) {
  return (
    <span className={`rounded px-2 py-0.5 text-[11px] ${STATUS_TONE[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

export function Breadcrumb({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav className="flex items-center gap-2 text-xs text-neutral-500">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span aria-hidden>/</span>}
          {item.href ? (
            <Link href={item.href} className="hover:text-neutral-300">
              {item.label}
            </Link>
          ) : (
            <span className="text-neutral-300">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="flex items-start justify-between gap-6 border-b border-neutral-800 pb-5">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-neutral-400">{subtitle}</p>}
      </div>
      {children}
    </header>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-neutral-800 px-6 py-12 text-center text-sm text-neutral-500">
      {children}
    </div>
  );
}
