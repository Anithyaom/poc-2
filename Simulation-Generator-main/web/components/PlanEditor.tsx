'use client';

import { useState } from 'react';
import type {
  ParameterOption,
  ParameterType,
  Plan,
  PlanParameter,
  PlanReadout,
  VisualElement,
} from '@/lib/types';

interface Props {
  plan: Plan;
  onChange: (plan: Plan) => void;
  readOnly?: boolean;
}

const inputClass =
  'w-full rounded-lg border border-neutral-800 bg-neutral-950/70 px-3 py-2 text-sm text-neutral-200 outline-none transition focus:border-cyan-700 disabled:cursor-default disabled:bg-transparent disabled:text-neutral-300';

function Section({
  number,
  title,
  description,
  action,
  children,
}: {
  number: string;
  title: string;
  description: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="grid gap-5 border-t border-neutral-800/80 pt-8 md:grid-cols-[180px_1fr]">
      <header>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-500/70">
              {number}
            </p>
            <h2 className="mt-2 text-sm font-semibold text-neutral-100">{title}</h2>
          </div>
          {action}
        </div>
        <p className="mt-2 text-xs leading-relaxed text-neutral-500">{description}</p>
      </header>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

type SectionId =
  | 'summary'
  | 'purpose'
  | 'experience'
  | 'controls'
  | 'visuals'
  | 'readouts'
  | 'behavior'
  | 'observations';

/** Holds the sections a teacher checks rather than decides on: visuals and behavior rules.
 *  They stay in the blueprint — call #2 needs them — but they open only on request. */
function CollapsibleSection({
  title,
  description,
  summary,
  open,
  onToggle,
  children,
}: {
  title: string;
  description: string;
  summary: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-neutral-800/80 pt-8">
      <div className="rounded-2xl border border-dashed border-neutral-800 bg-neutral-900/20 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-neutral-100">{title}</h2>
            <p className="mt-1.5 max-w-xl text-xs leading-relaxed text-neutral-500">{description}</p>
          </div>
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={open}
            className="shrink-0 rounded-lg border border-neutral-700 px-3 py-1.5 text-[11px] text-neutral-300 transition hover:border-cyan-800 hover:text-cyan-300"
          >
            {open ? 'Hide details' : `Show details — ${summary}`}
          </button>
        </div>
        {open && (
          <div className="mt-6 space-y-8 border-t border-neutral-800/70 pt-6">{children}</div>
        )}
      </div>
    </section>
  );
}

function DetailGroup({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-100">{title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-neutral-500">{description}</p>
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function EditButton({ editing, onClick }: { editing: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={editing
        ? 'rounded-md bg-cyan-500 px-2.5 py-1 text-[11px] font-medium text-neutral-950'
        : 'rounded-md border border-neutral-800 px-2.5 py-1 text-[11px] text-neutral-400 transition hover:border-neutral-700 hover:text-neutral-200'}
    >
      {editing ? 'Done' : 'Edit'}
    </button>
  );
}

function ReadBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">{label}</h3>
      <div className="mt-2 text-[15px] leading-7 text-neutral-300">{children}</div>
    </div>
  );
}

function ReadList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2.5">
      {items.map((item, index) => (
        <li key={index} className="flex gap-3 text-[15px] leading-7 text-neutral-300">
          <span className="mt-3 size-1.5 shrink-0 rounded-full bg-cyan-500/70" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function controlConfiguration(control: PlanParameter) {
  if (control.type === 'toggle') return control.default ? 'On by default' : 'Off by default';
  if (control.type === 'dropdown') {
    const labels = (control.options ?? []).map((option) => option.label).join(', ');
    const defaultLabel = control.options?.find((option) => option.value === control.default)?.label;
    return `${labels}${defaultLabel ? ` · Default: ${defaultLabel}` : ''}`;
  }
  const unit = control.unit ? ` ${control.unit}` : '';
  return `${control.min}–${control.max}${unit} · Step ${control.step} · Default ${control.default}${unit}`;
}

function ControlOverview({ control }: { control: PlanParameter }) {
  const typeLabel = control.type === 'number' ? 'Number input' : control.type;
  return (
    <div className="rounded-xl border border-neutral-800/80 bg-neutral-900/20 px-4 py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-neutral-100">{control.label}</h3>
        <span className="rounded-full bg-neutral-800 px-2.5 py-1 text-[10px] capitalize text-neutral-400">
          {typeLabel}
        </span>
      </div>
      <p className="mt-2 text-xs text-cyan-200/70">{controlConfiguration(control)}</p>
      <p className="mt-2 text-sm leading-6 text-neutral-400">{control.rationale}</p>
    </div>
  );
}

function TextArea({
  label,
  value,
  onChange,
  readOnly,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  rows?: number;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-neutral-500">
        {label}
      </span>
      <textarea
        value={value}
        rows={rows}
        disabled={readOnly}
        onChange={(event) => onChange(event.target.value)}
        className={`${inputClass} resize-y leading-relaxed`}
      />
    </label>
  );
}

function StringList({
  items,
  onChange,
  readOnly,
  addLabel,
}: {
  items: string[];
  onChange: (items: string[]) => void;
  readOnly?: boolean;
  addLabel: string;
}) {
  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={index} className="flex items-start gap-2">
          <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-cyan-500/70" />
          <textarea
            rows={2}
            disabled={readOnly}
            value={item}
            onChange={(event) =>
              onChange(items.map((current, itemIndex) =>
                itemIndex === index ? event.target.value : current,
              ))
            }
            className={`${inputClass} resize-y`}
          />
          {!readOnly && items.length > 1 && (
            <button
              type="button"
              onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}
              aria-label={`Remove item ${index + 1}`}
              className="mt-1 rounded-md px-2 py-1 text-neutral-600 transition hover:bg-neutral-900 hover:text-red-300"
            >
              ×
            </button>
          )}
        </div>
      ))}
      {!readOnly && (
        <button
          type="button"
          onClick={() => onChange([...items, ''])}
          className="rounded-md border border-dashed border-neutral-700 px-3 py-2 text-xs text-neutral-400 transition hover:border-cyan-800 hover:text-cyan-300"
        >
          + {addLabel}
        </button>
      )}
    </div>
  );
}

function nextId(prefix: string, ids: string[]) {
  let number = ids.length + 1;
  while (ids.includes(`${prefix}_${number}`)) number += 1;
  return `${prefix}_${number}`;
}

function controlForType(control: PlanParameter, type: ParameterType): PlanParameter {
  if (type === 'toggle') {
    return { ...control, type, min: null, max: null, step: null, unit: null, options: null, default: false };
  }
  if (type === 'dropdown') {
    const options = [
      { value: 'option_1', label: 'Option 1' },
      { value: 'option_2', label: 'Option 2' },
    ];
    return { ...control, type, min: null, max: null, step: null, unit: null, options, default: options[0].value };
  }
  return { ...control, type, min: 0, max: 100, step: 1, unit: null, options: null, default: 50 };
}

function NumberField({
  label,
  value,
  onChange,
  readOnly,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  readOnly?: boolean;
}) {
  return (
    <label>
      <span className="mb-1 block text-[10px] uppercase tracking-wide text-neutral-600">{label}</span>
      <input
        type="number"
        step="any"
        disabled={readOnly}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value === '' ? null : Number(event.target.value))}
        className={inputClass}
      />
    </label>
  );
}

function ControlCard({
  control,
  onChange,
  onRemove,
  canRemove,
  readOnly,
}: {
  control: PlanParameter;
  onChange: (control: PlanParameter) => void;
  onRemove: () => void;
  canRemove: boolean;
  readOnly?: boolean;
}) {
  const updateOptions = (options: ParameterOption[]) => {
    const defaultExists = options.some((option) => option.value === control.default);
    onChange({ ...control, options, default: defaultExists ? control.default : (options[0]?.value ?? '') });
  };

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/30 p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="min-w-0 flex-1">
          <span className="mb-1 block text-[10px] uppercase tracking-wide text-neutral-600">Control label</span>
          <input
            disabled={readOnly}
            value={control.label}
            onChange={(event) => onChange({ ...control, label: event.target.value })}
            className={inputClass}
          />
        </label>
        <label className="sm:w-36">
          <span className="mb-1 block text-[10px] uppercase tracking-wide text-neutral-600">Control type</span>
          <select
            disabled={readOnly}
            value={control.type}
            onChange={(event) => onChange(controlForType(control, event.target.value as ParameterType))}
            className={inputClass}
          >
            <option value="slider">Slider</option>
            <option value="dropdown">Dropdown</option>
            <option value="toggle">Toggle</option>
            <option value="number">Number input</option>
          </select>
        </label>
        {!readOnly && canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="self-end rounded-lg px-3 py-2 text-xs text-neutral-500 hover:bg-red-950/30 hover:text-red-300"
          >
            Remove
          </button>
        )}
      </div>

      <label className="mt-3 block">
        <span className="mb-1 block text-[10px] uppercase tracking-wide text-neutral-600">Why students change it</span>
        <textarea
          rows={2}
          disabled={readOnly}
          value={control.rationale}
          onChange={(event) => onChange({ ...control, rationale: event.target.value })}
          className={`${inputClass} resize-y`}
        />
      </label>

      {(control.type === 'slider' || control.type === 'number') && (
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <NumberField label="Minimum" value={control.min} readOnly={readOnly} onChange={(min) => onChange({ ...control, min })} />
          <NumberField label="Maximum" value={control.max} readOnly={readOnly} onChange={(max) => onChange({ ...control, max })} />
          <NumberField label="Step" value={control.step} readOnly={readOnly} onChange={(step) => onChange({ ...control, step })} />
          <NumberField label="Default" value={typeof control.default === 'number' ? control.default : null} readOnly={readOnly} onChange={(value) => onChange({ ...control, default: value ?? 0 })} />
          <label>
            <span className="mb-1 block text-[10px] uppercase tracking-wide text-neutral-600">Unit</span>
            <input disabled={readOnly} value={control.unit ?? ''} onChange={(event) => onChange({ ...control, unit: event.target.value || null })} className={inputClass} />
          </label>
        </div>
      )}

      {control.type === 'toggle' && (
        <label className="mt-3 flex items-center gap-2 text-xs text-neutral-400">
          <input type="checkbox" disabled={readOnly} checked={control.default === true} onChange={(event) => onChange({ ...control, default: event.target.checked })} />
          Enabled by default
        </label>
      )}

      {control.type === 'dropdown' && (
        <div className="mt-3 space-y-2">
          <p className="text-[10px] uppercase tracking-wide text-neutral-600">Options</p>
          {(control.options ?? []).map((option, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                disabled={readOnly}
                value={option.label}
                aria-label={`Option ${index + 1} label`}
                onChange={(event) => updateOptions((control.options ?? []).map((current, optionIndex) => optionIndex === index ? { ...current, label: event.target.value } : current))}
                className={inputClass}
              />
              <label className="flex shrink-0 items-center gap-1 text-[10px] text-neutral-500">
                <input type="radio" name={`default-${control.id}`} disabled={readOnly} checked={control.default === option.value} onChange={() => onChange({ ...control, default: option.value })} />
                default
              </label>
              {!readOnly && (control.options?.length ?? 0) > 2 && (
                <button type="button" aria-label={`Remove option ${index + 1}`} onClick={() => updateOptions((control.options ?? []).filter((_, optionIndex) => optionIndex !== index))} className="px-2 text-neutral-600 hover:text-red-300">×</button>
              )}
            </div>
          ))}
          {!readOnly && (
            <button
              type="button"
              onClick={() => {
                const options = control.options ?? [];
                const value = nextId('option', options.map((option) => option.value));
                const label = `Option ${options.length + 1}`;
                updateOptions([...options, { value, label }]);
              }}
              className="text-xs text-cyan-400 hover:text-cyan-300"
            >
              + Add option
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** The sections that live inside the collapsible detail block. */
const BLOCK_SECTIONS: SectionId[] = ['visuals', 'behavior'];

function detailSummary(plan: Plan) {
  const visuals = plan.visual_elements.length;
  const rules = plan.behavior_rules.length;
  return `${visuals} visual${visuals === 1 ? '' : 's'} · ${rules} rule${rules === 1 ? '' : 's'}`;
}

export function PlanEditor({ plan, onChange, readOnly }: Props) {
  const [editing, setEditing] = useState<SectionId | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const activeEditing = readOnly ? null : editing;
  const update = (patch: Partial<Plan>) => onChange({ ...plan, ...patch });
  const updateControl = (id: string, control: PlanParameter) =>
    update({ controls: plan.controls.map((current) => current.id === id ? control : current) });

  const addControl = () => {
    const id = nextId('control', [...plan.controls.map((control) => control.id), ...plan.readouts.map((readout) => readout.id)]);
    update({
      controls: [...plan.controls, {
        id,
        label: 'New control',
        type: 'slider',
        min: 0,
        max: 100,
        step: 1,
        unit: null,
        options: null,
        default: 50,
        rationale: 'Describe what students discover by changing this.',
      }],
    });
  };

  const addReadout = () => {
    const id = nextId('readout', [...plan.controls.map((control) => control.id), ...plan.readouts.map((readout) => readout.id)]);
    update({ readouts: [...plan.readouts, { id, label: 'New value', unit: null, description: 'Describe what this value communicates.' }] });
  };

  // Editing a section inside the detail block force-opens it, so a form is never mounted invisibly.
  const startEdit = (section: SectionId) => {
    if (BLOCK_SECTIONS.includes(section)) setDetailsOpen(true);
    setEditing(activeEditing === section ? null : section);
  };

  // Closing the block cancels an edit it would otherwise swallow.
  const toggleDetails = () => {
    if (detailsOpen && activeEditing && BLOCK_SECTIONS.includes(activeEditing)) setEditing(null);
    setDetailsOpen(!detailsOpen);
  };

  const editAction = (section: SectionId) => readOnly ? undefined : (
    <EditButton editing={activeEditing === section} onClick={() => startEdit(section)} />
  );

  return (
    <article className="space-y-10">
      <div className="overflow-hidden rounded-2xl border border-neutral-800 bg-gradient-to-br from-neutral-900/80 to-cyan-950/10">
        <div className="border-b border-neutral-800/80 px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-neutral-500">Understood as</p>
              <p className="mt-1 text-sm text-neutral-200">
                {plan.inferred_subject} <span className="text-neutral-600">/</span> {plan.inferred_topic}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-cyan-900/60 bg-cyan-950/30 px-3 py-1 text-[11px] text-cyan-300">Simulation blueprint</span>
              {editAction('summary')}
            </div>
          </div>
        </div>
        <div className="p-5 sm:p-6">
          {activeEditing === 'summary' ? (
            <div className="space-y-4">
              <label className="block">
                <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-neutral-500">Simulation title</span>
                <input value={plan.title} onChange={(event) => update({ title: event.target.value })} className={`${inputClass} text-lg font-semibold`} />
              </label>
              <TextArea label="Concept summary" value={plan.concept_summary} onChange={(concept_summary) => update({ concept_summary })} rows={2} />
            </div>
          ) : (
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-neutral-100">{plan.title}</h1>
              <p className="mt-3 max-w-3xl text-[15px] leading-7 text-neutral-300">{plan.concept_summary}</p>
            </div>
          )}
        </div>
      </div>

      <Section number="01" title="What it teaches" description="The purpose the generated simulation must serve." action={editAction('purpose')}>
        {activeEditing === 'purpose' ? (
          <div className="space-y-4">
            <TextArea label="Learning objective" value={plan.learning_objective} onChange={(learning_objective) => update({ learning_objective })} />
            <TextArea label="Where students go wrong" value={plan.misconception} onChange={(misconception) => update({ misconception })} />
          </div>
        ) : (
          <div className="space-y-7">
            <ReadBlock label="Learning objective">{plan.learning_objective}</ReadBlock>
            <ReadBlock label="Where students go wrong">{plan.misconception}</ReadBlock>
          </div>
        )}
      </Section>

      <Section number="02" title="What students should notice" description="Use these outcomes to check whether the generated simulation succeeds." action={editAction('observations')}>
        {activeEditing === 'observations'
          ? <StringList items={plan.expected_observations} onChange={(expected_observations) => update({ expected_observations })} addLabel="Add observation" />
          : <ReadList items={plan.expected_observations} />}
      </Section>

      <Section number="03" title="How it works" description="What students encounter and do inside the simulation." action={editAction('experience')}>
        {activeEditing === 'experience' ? (
          <div className="space-y-4">
            <TextArea label="Experience" value={plan.simulation_experience.summary} onChange={(summary) => update({ simulation_experience: { ...plan.simulation_experience, summary } })} />
            <TextArea label="Opening view" value={plan.simulation_experience.initial_state} onChange={(initial_state) => update({ simulation_experience: { ...plan.simulation_experience, initial_state } })} />
            <div>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-neutral-500">Student actions</p>
              <StringList items={plan.simulation_experience.student_actions} onChange={(student_actions) => update({ simulation_experience: { ...plan.simulation_experience, student_actions } })} addLabel="Add action" />
            </div>
            <TextArea label="End or reset state" value={plan.simulation_experience.completion_state} onChange={(completion_state) => update({ simulation_experience: { ...plan.simulation_experience, completion_state } })} />
            <label className="flex items-center gap-2 text-xs text-neutral-400">
              <input type="checkbox" checked={plan.time_stepped} onChange={(event) => update({ time_stepped: event.target.checked })} />
              Students can step, run, pause and reset it
            </label>
          </div>
        ) : (
          <div className="space-y-7">
            <ReadBlock label="Experience">{plan.simulation_experience.summary}</ReadBlock>
            <ReadBlock label="Opening view">{plan.simulation_experience.initial_state}</ReadBlock>
            <ReadBlock label="Student actions"><ReadList items={plan.simulation_experience.student_actions} /></ReadBlock>
            <ReadBlock label="End or reset state">{plan.simulation_experience.completion_state}</ReadBlock>
            <ReadBlock label="Playback">
              {plan.time_stepped
                ? 'Students can step, run, pause and reset the simulation.'
                : 'The simulation updates instantly; there is nothing to play or pause.'}
            </ReadBlock>
            <p className="text-xs italic text-neutral-500">
              Specified below: {detailSummary(plan)}.
            </p>
          </div>
        )}
      </Section>

      <Section number="04" title="What students can change" description="Choose the controls and how each one behaves." action={editAction('controls')}>
        {activeEditing === 'controls' ? (
          <div className="space-y-3">
            {plan.controls.map((control) => (
              <ControlCard key={control.id} control={control} canRemove={plan.controls.length > 1} onChange={(next) => updateControl(control.id, next)} onRemove={() => update({ controls: plan.controls.filter((current) => current.id !== control.id) })} />
            ))}
            <button type="button" onClick={addControl} className="w-full rounded-xl border border-dashed border-neutral-700 py-3 text-xs text-neutral-400 transition hover:border-cyan-800 hover:bg-cyan-950/10 hover:text-cyan-300">+ Add control</button>
          </div>
        ) : (
          <div className="space-y-3">
            {plan.controls.map((control) => <ControlOverview key={control.id} control={control} />)}
          </div>
        )}
      </Section>

      <Section number="05" title="Values displayed" description="Computed information students can read while exploring." action={editAction('readouts')}>
        {activeEditing === 'readouts' ? (
          <div className="space-y-3">
            {plan.readouts.map((readout, index) => (
              <div key={readout.id} className="rounded-xl border border-neutral-800 bg-neutral-900/30 p-4">
                <div className="grid gap-3 sm:grid-cols-[1fr_120px_auto]">
                  <label><span className="mb-1 block text-[10px] uppercase tracking-wide text-neutral-600">Label</span><input value={readout.label} onChange={(event) => update({ readouts: plan.readouts.map((current, readoutIndex): PlanReadout => readoutIndex === index ? { ...current, label: event.target.value } : current) })} className={inputClass} /></label>
                  <label><span className="mb-1 block text-[10px] uppercase tracking-wide text-neutral-600">Unit</span><input value={readout.unit ?? ''} onChange={(event) => update({ readouts: plan.readouts.map((current, readoutIndex): PlanReadout => readoutIndex === index ? { ...current, unit: event.target.value || null } : current) })} className={inputClass} /></label>
                  <button type="button" onClick={() => update({ readouts: plan.readouts.filter((_, readoutIndex) => readoutIndex !== index) })} className="self-end rounded-lg px-3 py-2 text-xs text-neutral-500 hover:bg-red-950/30 hover:text-red-300">Remove</button>
                </div>
                <textarea rows={2} value={readout.description} onChange={(event) => update({ readouts: plan.readouts.map((current, readoutIndex): PlanReadout => readoutIndex === index ? { ...current, description: event.target.value } : current) })} className={`${inputClass} mt-3 resize-y`} />
              </div>
            ))}
            <button type="button" onClick={addReadout} className="rounded-md border border-dashed border-neutral-700 px-3 py-2 text-xs text-neutral-400 hover:border-cyan-800 hover:text-cyan-300">+ Add displayed value</button>
          </div>
        ) : plan.readouts.length > 0 ? (
          <div className="overflow-hidden rounded-xl border border-neutral-800/80">
            {plan.readouts.map((readout) => (
              <div key={readout.id} className="grid gap-1 border-b border-neutral-800/70 px-4 py-3.5 last:border-0 sm:grid-cols-[180px_1fr]">
                <div className="text-sm font-medium text-neutral-100">{readout.label}{readout.unit ? <span className="ml-1 font-normal text-neutral-500">({readout.unit})</span> : null}</div>
                <p className="text-sm leading-6 text-neutral-400">{readout.description}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm italic text-neutral-500">No numeric readouts are required for this simulation.</p>
        )}
      </Section>

      <CollapsibleSection
        title="What the simulation will show and do"
        description="The visuals and rules the simulation is built from. Open this to check or change them."
        summary={detailSummary(plan)}
        open={detailsOpen}
        onToggle={toggleDetails}
      >
        <DetailGroup title="What appears on screen" description="The important visuals the simulation must draw." action={editAction('visuals')}>
          {activeEditing === 'visuals' ? (
            <div className="space-y-3">
              {plan.visual_elements.map((element, index) => (
                <div key={index} className="rounded-xl border border-neutral-800 bg-neutral-900/30 p-4">
                  <div className="flex gap-2">
                    <input value={element.name} onChange={(event) => update({ visual_elements: plan.visual_elements.map((current, elementIndex): VisualElement => elementIndex === index ? { ...current, name: event.target.value } : current) })} className={`${inputClass} font-medium`} />
                    {plan.visual_elements.length > 1 && <button type="button" aria-label={`Remove visual ${index + 1}`} onClick={() => update({ visual_elements: plan.visual_elements.filter((_, elementIndex) => elementIndex !== index) })} className="px-2 text-neutral-600 hover:text-red-300">×</button>}
                  </div>
                  <textarea rows={2} value={element.description} onChange={(event) => update({ visual_elements: plan.visual_elements.map((current, elementIndex): VisualElement => elementIndex === index ? { ...current, description: event.target.value } : current) })} className={`${inputClass} mt-2 resize-y`} />
                </div>
              ))}
              <button type="button" onClick={() => update({ visual_elements: [...plan.visual_elements, { name: 'New visual', description: 'Describe how it looks and changes.' }] })} className="rounded-md border border-dashed border-neutral-700 px-3 py-2 text-xs text-neutral-400 hover:border-cyan-800 hover:text-cyan-300">+ Add visual</button>
            </div>
          ) : (
            <div className="divide-y divide-neutral-800/70">
              {plan.visual_elements.map((element, index) => (
                <div key={index} className="py-4 first:pt-0 last:pb-0">
                  <h3 className="text-sm font-medium text-neutral-100">{element.name}</h3>
                  <p className="mt-1.5 text-[15px] leading-7 text-neutral-400">{element.description}</p>
                </div>
              ))}
            </div>
          )}
        </DetailGroup>

        <DetailGroup title="How it should behave" description="Rules the generated simulation must follow exactly." action={editAction('behavior')}>
          {activeEditing === 'behavior'
            ? <StringList items={plan.behavior_rules} onChange={(behavior_rules) => update({ behavior_rules })} addLabel="Add rule" />
            : <ReadList items={plan.behavior_rules} />}
        </DetailGroup>
      </CollapsibleSection>
    </article>
  );
}
