import type { Plan } from '@/lib/types';

/**
 * The left region of the workspace: the teacher's own approved blueprint, beside
 * the thing built from it.
 *
 * Every word here was reviewed and accepted on the blueprint screen — no model
 * wrote any of this at generation time, so it carries zero added risk and gives
 * the teacher something to check the simulation *against*. Deliberately only the
 * three fields that answer "is this right?": the objective, what to notice, and
 * where students go wrong. Controls and readouts live in the right panel where
 * they can be operated, and the rest of the blueprint is authoring detail that
 * would only crowd the screen.
 */
export function BlueprintContext({ plan }: { plan: Plan }) {
  return (
    <aside className="flex w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r border-neutral-800 p-5">
      <Block heading="What it teaches">{plan.learning_objective}</Block>

      <div>
        <Heading>What to notice</Heading>
        <ul className="mt-1.5 flex flex-col gap-2">
          {plan.expected_observations.map((observation) => (
            <li key={observation} className="flex gap-2 text-xs leading-relaxed text-neutral-400">
              <span aria-hidden className="text-neutral-600">
                ·
              </span>
              <span>{observation}</span>
            </li>
          ))}
        </ul>
      </div>

      <Block heading="Where students go wrong">{plan.misconception}</Block>
    </aside>
  );
}

function Heading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[10px] font-medium uppercase tracking-wider text-neutral-500">
      {children}
    </h2>
  );
}

function Block({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div>
      <Heading>{heading}</Heading>
      <p className="mt-1.5 text-xs leading-relaxed text-neutral-400">{children}</p>
    </div>
  );
}
