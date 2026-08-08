"""Host-authored design tokens, injected into every generated core.

The prompt *tells* the model to use these variables; this module *guarantees* they
exist. That asymmetry is the point — a core that invents its own palette still
renders, so nothing would ever fail loudly, and six simulations would quietly end
up looking like six different products.

Two consequences worth keeping:

- **Every stored core is restyleable without regenerating it.** Injection happens
  on the way in, but the token block is identifiable and replaceable, so tuning the
  palette later is a CSS edit rather than another 90-second call per simulation.
- **The model picks by meaning, never by hex.** `--sim-primary` is "the object
  under study", not "blue". That is what lets the palette change without every
  simulation's semantics changing with it.

The three series hues are validated, not chosen by eye: all-pairs CVD ΔE 9.2 and
normal-vision ΔE 24.0, both clear of the floors. A fourth slot would put yellow
beside orange and fail, which is exactly why the contract caps a core at three
tracked quantities. Aqua measures 2.74:1 on this surface, so the relief rule binds:
every distinct element carries a visible text label and colour never carries
identity alone.
"""

import re

# The marker is what makes this replaceable later. Never remove it.
_OPEN = "<style data-simgen-tokens>"
_CLOSE = "</style>"

CORE_TOKENS = f"""{_OPEN}
:root {{
  /* A light scene inside a dark shell: the simulation is the bright object on
     the page. Revisit if these are ever projected — projectors crush mid-tones. */
  color-scheme: light;
  --sim-surface:   #fcfcfb;   /* the scene itself */
  --sim-surface-2: #f0efec;   /* plot backgrounds, inset panels */
  --sim-grid:      #d9d8d4;   /* axes and gridlines — always recessive */
  --sim-ink:       #0b0b0b;
  --sim-ink-2:     #52514e;

  /* Roles, not colours. Pick by MEANING; never write a hex literal. */
  --sim-primary:   #2a78d6;   /* the object under study */
  --sim-secondary: #eb6834;   /* what it is compared against */
  --sim-tertiary:  #1baf7a;   /* a third tracked quantity */
  --sim-inactive:  #b8b7b2;   /* excluded, unreached, context */

  --sim-good:      #0ca30c;
  --sim-warn:      #fab219;
  --sim-critical:  #d03b3b;

  --sim-font: system-ui, -apple-system, "Segoe UI", sans-serif;
  --sim-mono: ui-monospace, "SF Mono", Menlo, monospace;
  --sim-text-sm:   12px;
  --sim-text:      14px;
  --sim-text-lg:   18px;
  --sim-space:     8px;
  --sim-radius:    6px;
  --sim-stroke:    2px;
}}

html, body {{
  margin: 0;
  height: 100%;
  background: var(--sim-surface);
  color: var(--sim-ink);
  font-family: var(--sim-font);
  font-size: var(--sim-text);
}}
{_CLOSE}"""

# Matches the injected block wherever it sits, so a re-injection replaces rather
# than stacks. Non-greedy: a core may legitimately carry other <style> tags.
_EXISTING = re.compile(re.escape(_OPEN) + r".*?" + re.escape(_CLOSE), re.DOTALL)

_HEAD_OPEN = re.compile(r"<head\b[^>]*>", re.IGNORECASE)


def inject_tokens(core_html: str) -> str:
    """Put the token block at the top of <head>, replacing any previous one.

    Top of head, not bottom: these are defaults the core's own CSS is expected to
    override where it needs to. A core that sets its own background should win —
    the tokens exist to make the *unstated* consistent, not to overrule intent.
    """
    core_html = _EXISTING.sub("", core_html)

    head = _HEAD_OPEN.search(core_html)
    if head:
        return core_html[: head.end()] + "\n" + CORE_TOKENS + core_html[head.end() :]

    # No <head> at all. The gate rejects documents this malformed, so this is a
    # belt-and-braces path: prepend rather than lose the tokens silently.
    return CORE_TOKENS + "\n" + core_html
