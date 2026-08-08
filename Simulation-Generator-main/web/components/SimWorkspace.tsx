'use client';

import { useCallback, useMemo, useRef, useState } from 'react';
import { BlueprintContext } from '@/components/BlueprintContext';
import { ControlPanel } from '@/components/ControlPanel';
import { SandboxedSimFrame, type SimFrameHandle } from '@/components/SandboxedSimFrame';
import type { ParameterValue, Plan, Simulation, TransportCommand } from '@/lib/types';

interface Props {
  simulation: Simulation;
  plan: Plan | null;
}

/**
 * The payoff screen, in three regions: the approved blueprint on the left, the
 * generated core in the middle, the shell's controls on the right.
 *
 * Only the middle region is generated. The two panels either side are ours, which
 * is the shell/core split made visible — a teacher can see what they approved
 * beside what was built, and every control they operate is host-rendered from the
 * manifest rather than drawn by the model.
 */
export function SimWorkspace({ simulation, plan }: Props) {
  const manifest = simulation.manifest_json;
  const defaults = useMemo(
    () => Object.fromEntries(manifest.parameters.map((p) => [p.id, p.default])),
    [manifest],
  );

  const [values, setValues] = useState<Record<string, ParameterValue>>(defaults);
  const [readouts, setReadouts] = useState<Record<string, number | string>>({});
  const [simError, setSimError] = useState<string | null>(null);
  const frameRef = useRef<SimFrameHandle>(null);

  const handleReadout = useCallback((next: Record<string, number | string>) => {
    setReadouts((prev) => ({ ...prev, ...next }));
  }, []);

  const transport = useCallback((command: TransportCommand) => {
    frameRef.current?.send(command);
  }, []);

  // Reset is both halves: the shell returns the controls to their defaults, and
  // sim:reset tells the core to rewind its own internal state (time, trails, step
  // count) — which no amount of parameter setting would do on its own.
  const reset = useCallback(() => {
    setValues(defaults);
    frameRef.current?.send('sim:reset');
  }, [defaults]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {simError && (
        <p className="border-b border-amber-900/60 bg-amber-950/20 px-5 py-2 text-xs text-amber-300">
          The simulation reported an error: {simError}
        </p>
      )}
      <div className="flex min-h-0 flex-1">
        {plan && <BlueprintContext plan={plan} />}
        <div className="min-w-0 flex-1">
          <SandboxedSimFrame
            ref={frameRef}
            coreHtml={simulation.core_html}
            values={values}
            onReadout={handleReadout}
            onError={setSimError}
          />
        </div>
        <ControlPanel
          manifest={manifest}
          values={values}
          readouts={readouts}
          onChange={(id, value) => setValues((prev) => ({ ...prev, [id]: value }))}
          onReset={reset}
          onTransport={transport}
        />
      </div>
    </div>
  );
}
