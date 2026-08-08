"""The shell/core contract, checked before anything is persisted.

Never trust LLM output. The core is generated code that we mount in an iframe and
drive by `postMessage`; if it ignores an id, skips the handshake, or draws its own
Run button, nothing crashes — the simulation just quietly fails to respond, which
is the single worst failure mode this pipeline has. A teacher cannot tell "the
model misunderstood the physics" from "the slider isn't wired up".

**This reads text; it does not run the simulation.** It proves the core *mentions*
`sim:ready`, not that it fires it. Executing the core needs a headless browser in
the worker image — real weight for a POC — so the teacher stays the runtime check.
Everything checked here is a failure a human reviewer would struggle to diagnose;
everything left unchecked is one they can see at a glance.
"""

import re

from src.llm.schemas import Manifest

# The handshake every core needs, whether or not it advances through time.
_REQUIRED = ("sim:init", "sim:set", "sim:ready", "sim:readout")

# Only when the manifest says the simulation steps. Read `manifest.time_stepped`
# once, here — if the transport bar ever becomes unconditional (handoff §5 item 8)
# this is the one line that changes.
_TRANSPORT = ("sim:play", "sim:pause", "sim:step", "sim:reset")

# Control UI the shell owns. Deliberately narrow: `<input type="range">` and
# friends are the violation, and a `<canvas>` full of drawn shapes is not.
_OWN_CONTROLS = re.compile(r"<(?:button|select|input\b(?![^>]*type=[\"']?(?:hidden)))", re.I)

# Same tag the prompt hands over verbatim. Checked by name, not by exact string:
# a model that reformats the attribute order has still blocked the network.
_CSP = re.compile(r"http-equiv=[\"']?Content-Security-Policy", re.I)
_CSP_BLOCKS_NETWORK = re.compile(r"default-src\s+'none'", re.I)


def validate_core(core_html: str, manifest: Manifest) -> list[str]:
    """Return the problems with this core. Empty means it is safe to persist.

    Phrased as instructions to the model, not as a report to a human: these strings
    are fed straight back into the retry, and that is the only audience that can
    act on them.
    """
    problems: list[str] = []
    head = core_html.lstrip()[:64].lower()

    if not head.startswith("<!doctype html"):
        problems.append("The document must start with <!doctype html>.")
    if "</html>" not in core_html.lower():
        problems.append("The document is incomplete — it has no closing </html> tag.")

    if not _CSP.search(core_html):
        problems.append("The Content-Security-Policy meta tag is missing from <head>.")
    elif not _CSP_BLOCKS_NETWORK.search(core_html):
        problems.append("The Content-Security-Policy must include default-src 'none'.")

    problems += [
        f"The core never handles the {message} message."
        for message in _REQUIRED
        if message not in core_html
    ]

    if manifest.time_stepped:
        problems += [
            f"This simulation is time-stepped, so it must handle {message}."
            for message in _TRANSPORT
            if message not in core_html
        ]

    if _OWN_CONTROLS.search(core_html):
        problems.append(
            "The core draws its own controls. The host renders every slider, toggle, "
            "dropdown and Step/Run/Pause/Reset button from the manifest — remove them "
            "and respond to the messages instead."
        )

    problems += [
        f"The approved id {identifier!r} is never used."
        for identifier in _approved_ids(manifest)
        if identifier not in core_html
    ]

    return problems


def _approved_ids(manifest: Manifest) -> list[str]:
    return [p.id for p in manifest.parameters] + [r.id for r in manifest.readouts]
