'use client';

import type { Manifest, Parameter, ParameterValue, TransportCommand } from '@/lib/types';

interface Props {
  manifest: Manifest;
  values: Record<string, ParameterValue>;
  onChange: (id: string, value: ParameterValue) => void;
  onReset: () => void;
  onTransport: (command: TransportCommand) => void;
  readouts: Record<string, number | string>;
}

/**
 * The transport bar. Step, Run, Pause and Reset are the same four actions for every
 * time-stepped simulation, so this is one fixed bar behind the manifest's
 * `time_stepped` flag — never a per-simulation list of buttons the model invents.
 * Keeping it here is what makes "the LLM never generates control UI" literally true.
 */
function TransportBar({
  onTransport,
  onReset,
}: {
  onTransport: (command: TransportCommand) => void;
  onReset: () => void;
}) {
  const buttons: [string, () => void][] = [
    ['Step', () => onTransport('sim:step')],
    ['Run', () => onTransport('sim:play')],
    ['Pause', () => onTransport('sim:pause')],
    ['Reset', onReset],
  ];

  return (
    <div className="flex gap-1.5">
      {buttons.map(([label, onClick]) => (
        <button
          key={label}
          type="button"
          onClick={onClick}
          className="flex-1 rounded-md border border-neutral-700 px-2 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/**
 * Readouts routinely span many orders of magnitude — an Arrhenius fraction is
 * ~3e-9 %, a rate ratio is ~400. Fixed 2-decimal precision renders the first as
 * "0.00", which looks like a dead simulation rather than a small number.
 */
function formatReadout(value: number | string) {
  if (typeof value !== 'number') return value;
  if (!Number.isFinite(value)) return '—';

  const magnitude = Math.abs(value);
  if (magnitude === 0) return '0';
  if (magnitude < 1e-3 || magnitude >= 1e6) return value.toExponential(2);
  if (magnitude < 1) return value.toPrecision(3);
  return value.toFixed(2);
}

function Control({
  param,
  value,
  onChange,
}: {
  param: Parameter;
  value: ParameterValue;
  onChange: (v: ParameterValue) => void;
}) {
  switch (param.type) {
    case 'slider':
      return (
        <input
          type="range"
          min={param.min ?? 0}
          max={param.max ?? 1}
          step={param.step ?? 0.01}
          value={Number(value)}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full accent-sky-400"
        />
      );
    case 'number':
      return (
        <input
          type="number"
          min={param.min ?? undefined}
          max={param.max ?? undefined}
          step={param.step ?? undefined}
          value={Number(value)}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
        />
      );
    case 'toggle':
      return (
        <button
          type="button"
          role="switch"
          aria-checked={Boolean(value)}
          onClick={() => onChange(!value)}
          className={`h-6 w-11 rounded-full transition-colors ${
            value ? 'bg-sky-400' : 'bg-neutral-700'
          }`}
        >
          <span
            className={`block h-5 w-5 rounded-full bg-white transition-transform ${
              value ? 'translate-x-5' : 'translate-x-0.5'
            }`}
          />
        </button>
      );
    case 'dropdown':
      return (
        <select
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
        >
          {(param.options ?? []).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      );
  }
}

/**
 * The shell. Rendered entirely from the manifest — the LLM never generates control UI,
 * so every simulation gets identical, on-brand controls.
 */
export function ControlPanel({
  manifest,
  values,
  onChange,
  onReset,
  onTransport,
  readouts,
}: Props) {
  return (
    <aside className="flex w-72 shrink-0 flex-col gap-6 overflow-y-auto border-l border-neutral-800 p-5">
      <div>
        <h2 className="text-base font-medium">{manifest.title}</h2>
        <p className="mt-1 text-xs text-neutral-400">{manifest.concept}</p>
      </div>

      {manifest.time_stepped && <TransportBar onTransport={onTransport} onReset={onReset} />}

      <div className="flex flex-col gap-5">
        {manifest.parameters.map((param) => (
          <label key={param.id} className="flex flex-col gap-2">
            <span className="flex items-baseline justify-between text-xs text-neutral-300">
              <span>{param.label}</span>
              {param.type !== 'toggle' && (
                <span className="font-mono text-neutral-500">
                  {String(values[param.id])}
                  {param.unit ? ` ${param.unit}` : ''}
                </span>
              )}
            </span>
            <Control
              param={param}
              value={values[param.id]}
              onChange={(v) => onChange(param.id, v)}
            />
          </label>
        ))}
      </div>

      {manifest.readouts.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-neutral-800 pt-4">
          {manifest.readouts.map((r) => (
            <div key={r.id} className="flex items-baseline justify-between text-xs">
              <span className="text-neutral-400">{r.label}</span>
              <span className="font-mono text-sky-300">
                {r.id in readouts ? formatReadout(readouts[r.id]) : '—'}
                {r.unit ? ` ${r.unit}` : ''}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="mt-auto flex flex-col gap-6">
        {/* The transport bar already owns Reset; two of them would invite two meanings. */}
        {!manifest.time_stepped && (
          <button
            type="button"
            onClick={onReset}
            className="rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800"
          >
            Reset to defaults
          </button>
        )}

        <p className="text-[11px] leading-relaxed text-neutral-500">{manifest.learning_goal}</p>
      </div>
    </aside>
  );
}
