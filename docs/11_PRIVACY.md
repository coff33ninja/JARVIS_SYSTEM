# 11 — Privacy & Security Review

Local-first by default (ADR-005). This document records the data flows, threats, and mitigations. Review again before any phase ships.

## Data inventory

| Data | Where it lives | Default behavior |
|---|---|---|
| Webcam frames | RAM only; never stored | discarded each frame |
| Hand/pose/face landmarks | RAM | transient, used for control |
| Screen captures (for "what am I pointing at") | RAM, one-shot | sent to vision model only when a tool calls it |
| Voice audio (wake/STT) | RAM, short buffer | discarded after transcription |
| Transferred files | LAN path PC↔device | encrypted transport (LocalSend) |
| Local chat/agent logs | `logs/` on disk | local; configurable retention |
| LLM prompts / screen context | Local model by default; cloud only if opt-in | see opt-in policy below |

## Threats & mitigations

| # | Threat | Mitigation |
|---|---|---|
| T1 | Camera recording without consent | Visible HUD camera indicator; camera kill switch (hotkey + tray + software off); frames never written to disk |
| T2 | Sensitive screen content leaks to cloud | Local-only mode flag; "what am I pointing at" sends screenshots ONLY to local vision model by default; cloud vision requires explicit per-feature opt-in |
| T3 | Voice captured unintentionally | Wake word gating; mic auto-mute outside Chat mode; audio buffer ring with hard size cap |
| T4 | Files intercepted on LAN | Use LocalSend's encrypted transport; bind transfer server to LAN interface; no WAN exposure |
| T5 | Prompt injection via on-screen text | When reading screenshots into the model, delimit content and instruct the model to treat it as data, never instructions; agent confirms before destructive actions |
| T6 | Unauthorized control of the machine | Gesture confidence thresholds + mode machine reduce accidental triggers; optional face unlock so the system only responds to the owner (Phase 6) |
| T7 | Stored logs contain secrets | Redact API keys/tokens in logs; never log full prompts of cloud APIs |

## Opt-in cloud policy

- Cloud LLM/vision APIs are **off by default**.
- Each cloud feature has its own toggle + visible on-HUD indicator (e.g., "CLOUD: GPT-4o" badge).
- When off, the agent degrades to the local model (or reports unavailable) rather than silently sending data out.

## Controls to build

- [ ] Camera kill switch (hotkey + tray + overlay indicator)
- [ ] Local-only mode (config flag that forces all inference + vision local)
- [ ] Mic auto-mute outside Chat mode
- [ ] Log redaction for keys/tokens
- [ ] Per-feature cloud toggles + HUD badges
- [ ] Optional face unlock (Phase 6)
- [ ] Transfer allowlist (only known devices, not "any peer")
