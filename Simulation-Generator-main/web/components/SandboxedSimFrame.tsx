'use client';

import { useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react';
import type { ParameterValue, TransportCommand } from '@/lib/types';

/** Lets the shell's transport bar reach the core. Commands are events, not state. */
export interface SimFrameHandle {
  send: (command: TransportCommand) => void;
}

interface Props {
  coreHtml: string;
  values: Record<string, ParameterValue>;
  onReadout: (values: Record<string, number | string>) => void;
  onError: (message: string) => void;
  ref?: Ref<SimFrameHandle>;
}

/**
 * Mounts the LLM-generated core in a sandboxed iframe and drives it over postMessage.
 *
 * Sandbox discipline (spec §7.2): `allow-scripts` WITHOUT `allow-same-origin`, so
 * the core cannot reach the parent app, cookies, or storage. The core also carries
 * a network-blocking CSP of its own. Don't loosen either — this is generated code.
 */
export function SandboxedSimFrame({ coreHtml, values, onReadout, onError, ref }: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [readyCore, setReadyCore] = useState<string | null>(null);
  const ready = readyCore === coreHtml;
  const sentRef = useRef<{
    coreHtml: string | null;
    values: Record<string, ParameterValue>;
  }>({ coreHtml: null, values: {} });

  // Run commands are one-shot events, so they are pushed imperatively rather than
  // mirrored into state the way parameter values are. Dropped before sim:ready —
  // the core has no listener attached yet, and there is nothing to queue for.
  useImperativeHandle(
    ref,
    () => ({
      send: (command: TransportCommand) => {
        if (!ready) return;
        frameRef.current?.contentWindow?.postMessage({ type: command }, '*');
      },
    }),
    [ready],
  );

  // A null-origin iframe reports event.origin === 'null', so identity is checked by
  // comparing against our own contentWindow rather than by origin.
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.source !== frameRef.current?.contentWindow) return;
      const data = event.data;
      if (!data || typeof data !== 'object') return;

      switch (data.type) {
        case 'sim:ready':
          setReadyCore(coreHtml);
          break;
        case 'sim:readout':
          if (data.values) onReadout(data.values);
          break;
        case 'sim:error':
          onError(String(data.message ?? 'Unknown simulation error'));
          break;
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [coreHtml, onReadout, onError]);

  // sim:init once the core announces itself, then one sim:set per changed control.
  useEffect(() => {
    const win = frameRef.current?.contentWindow;
    if (!ready || !win) return;

    if (sentRef.current.coreHtml !== coreHtml) {
      win.postMessage({ type: 'sim:init', params: values }, '*');
      sentRef.current = { coreHtml, values: { ...values } };
      return;
    }

    for (const [id, value] of Object.entries(values)) {
      if (sentRef.current.values[id] !== value) {
        win.postMessage({ type: 'sim:set', id, value }, '*');
        sentRef.current.values[id] = value;
      }
    }
  }, [coreHtml, ready, values]);

  return (
    <iframe
      ref={frameRef}
      title="Simulation"
      sandbox="allow-scripts"
      srcDoc={coreHtml}
      className="h-full w-full border-0 bg-neutral-950"
    />
  );
}
