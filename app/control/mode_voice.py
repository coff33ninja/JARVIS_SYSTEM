"""Voice commands for mode switching: "jarvis, chat mode" -> Mode.CHAT.

The mode table (app/control/modes.py) already defines the ``VOICE`` trigger;
this module supplies the missing wiring that translates a spoken phrase into
the right sequence of transitions. Routing is done by BFS over the transition
table so any source mode can reach any target mode through the shortest valid
path (e.g. TRANSFER -> CHAT = spread-toggle, then voice-toggle).

Usage from the voice loop::

    voice = VoiceLoop(agent, stt, tts, mic,
                      on_command=lambda cmd: handle_mode_command(cmd, modes))

``handle_mode_command`` returns a confirmation phrase for the TTS when it
handled the command, or ``None`` when the phrase wasn't a mode command (so the
agent still runs).
"""

from __future__ import annotations

from typing import Optional

from .modes import Mode, ModeMachine, _TRANSITIONS

# Phrase substrings -> target mode. Ordered so longer/overlapping phrases win.
PHRASE_TARGETS: tuple[tuple[str, Mode], ...] = (
    ("presentation", Mode.PRESENTATION),
    ("present mode", Mode.PRESENTATION),
    ("present", Mode.PRESENTATION),
    ("transfer", Mode.TRANSFER),
    ("chat", Mode.CHAT),
    ("control mode", Mode.CONTROL),
    ("control", Mode.CONTROL),
    ("idle", Mode.IDLE),
)

_MODE_REPLY = {
    Mode.IDLE: "Idle.",
    Mode.CONTROL: "Control mode.",
    Mode.CHAT: "Chat mode.",
    Mode.TRANSFER: "Transfer mode.",
    Mode.PRESENTATION: "Presentation mode.",
}

_ADJACENCY: Optional[dict[Mode, list[tuple[str, Mode]]]] = None


def parse_mode_command(command: str) -> Optional[Mode]:
    """Return the target mode for a voice command, or None if not one."""
    low = command.lower()
    for phrase, target in PHRASE_TARGETS:
        if phrase in low:
            return target
    return None


def route_to(modes: ModeMachine, target: Mode) -> Mode:
    """Move ``modes`` to ``target`` via the shortest valid transition path.

    Idempotent: if already at ``target`` (or unreachable), no-op.
    """
    if modes.mode is target:
        return modes.mode
    path = _shortest_path(modes.mode, target)
    if path is None:
        return modes.mode
    for trigger in path:
        modes.transition(trigger)
    return modes.mode


def handle_mode_command(command: str, modes: ModeMachine) -> Optional[str]:
    """Handle a mode-switch phrase. Returns a TTS reply, or None if not one."""
    target = parse_mode_command(command)
    if target is None:
        return None
    route_to(modes, target)
    return _MODE_REPLY[target]


# --------------------------------------------------------------------- #
# BFS over the transition table
# --------------------------------------------------------------------- #

def _adjacency() -> dict[Mode, list[tuple[str, Mode]]]:
    global _ADJACENCY
    if _ADJACENCY is None:
        adj: dict[Mode, list[tuple[str, Mode]]] = {}
        for (source, trigger), dst in _TRANSITIONS.items():
            adj.setdefault(source, []).append((trigger, dst))
        _ADJACENCY = adj
    return _ADJACENCY


def _shortest_path(source: Mode, target: Mode) -> Optional[list[str]]:
    """BFS: the list of triggers that take ``source`` to ``target``."""
    if source is target:
        return []
    prev: dict[Mode, tuple[Mode, str]] = {}
    seen = {source}
    frontier = [source]
    while frontier:
        node = frontier.pop(0)
        for trigger, nxt in _adjacency().get(node, ()):
            if nxt in seen:
                continue
            prev[nxt] = (node, trigger)
            if nxt is target:
                return _reconstruct(prev, source, target)
            seen.add(nxt)
            frontier.append(nxt)
    return None


def _reconstruct(prev: dict[Mode, tuple[Mode, str]], source: Mode,
                 target: Mode) -> list[str]:
    triggers: list[str] = []
    cur = target
    while cur is not source:
        cur, trigger = prev[cur]
        triggers.append(trigger)
    return list(reversed(triggers))
