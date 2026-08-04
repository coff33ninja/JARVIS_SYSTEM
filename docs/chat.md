# MediaPipe Self-Hosted Edge Projects — Source Chat (Grok)

> Original research conversation this project was scaffolded from. Reproduced here as a static reference. See `01_REFERENCES.md` for the categorized/verified link catalog, and `README.md` / `02_PROJECT_PLAN.md`–`06_DECISIONS.md` for the distilled planning docs derived from it.

**Share link:** https://grok.com/share/bGVnYWN5LWNvcHk_645b467c-b75b-4fde-a9a8-e6d5bff227af

---

## Q1: Self hosted and cloud projects around mediapipe

MediaPipe (now under Google AI Edge) is primarily an on-device / edge ML framework for real-time vision, audio, and text tasks (pose, hands, face landmarks, gesture recognition, object detection, segmentation, etc.). True "cloud-native" projects are less common because the design favors local inference for privacy and low latency, but there are solid self-hosted options and ways to serve it remotely.

### Official Resources

- **Core repo:** `google-ai-edge/mediapipe` — Framework + Solutions (Tasks APIs). Supports Docker builds for the C++ framework and Python wheels (including Raspberry Pi / aarch64).
- **Samples:** `google-ai-edge/mediapipe-samples` and the web-focused `mediapipe-samples-web` (browser demos that run fully client-side).
- **Docs & Studio:** developers.google.com/edge/mediapipe — Instant browser demos, Python/JS/Android/iOS setup, Model Maker for customization.
- Docker support is built-in (official Dockerfiles for building wheels and the framework).

### Notable Self-Hosted / Edge Projects

These emphasize local processing (no data leaves the device):

| Project | Description | Key Tech / Platform | Link |
|---|---|---|---|
| DeskPulse | Privacy-first real-time posture monitoring. Runs as a systemd service, local alerts, progress tracking. Zero cloud dependencies. | MediaPipe Tasks Pose Landmarker, Flask, Raspberry Pi 4/5 (4GB+ recommended) | EmekaOkaforTech/deskpulse |
| StreamPoseML | End-to-end toolkit + web app for real-time video pose classification. Extract keypoints with MediaPipe, build datasets, train models, deploy live classification (webcam or video). Docker support. | MediaPipe BlazePose, Python package + web UI, Docker | mrilikecoding/StreamPoseML (also on PyPI as `stream-pose-ml`) |
| Self Care Selfies | Video analysis pipeline for patient selfies (e.g., neurological metrics). Processes uploaded videos with MediaPipe landmarks → motion metrics CSV. Headless/server-friendly. | MediaPipe (≥0.10.30), Python | UCSF-MSLAB/self_care_selfies |
| GestureSensor | Detects faces + gestures and publishes results via MQTT. Docker-ready. | MediaPipe + custom NN for gestures | mmcc-xx/gesturesensor |
| SaraKIT Face Analysis | Face detection / landmarks / mesh optimized for Raspberry Pi 64-bit. Browser preview. | MediaPipe on RPi | SaraEye/SaraKIT-... |
| Official RPi examples | Gesture recognizer and other Tasks running on Raspberry Pi camera. | MediaPipe Tasks | In mediapipe-samples (e.g., `examples/gesture_recognizer/raspberry_pi`) |

Other community mentions include edge pipeline experiments (e.g., Edgepipes as a pure-Python MediaPipe-inspired framework) and various RPi/Docker object-detection or face setups.

### Cloud / Server-Side / Hybrid Deployments

MediaPipe graphs can be served remotely (useful when clients send frames and a powerful backend runs inference):

- **OpenVINO Model Server (OVMS):** Strongest production option for serving MediaPipe graphs. Supports gRPC/REST (unary + streaming), stateful graphs, OpenVINO-accelerated calculators, multi-model pipelines, and Docker/Kubernetes deployment. Repo: `openvinotoolkit/model_server` (see `docs/mediapipe.md` and `demos/mediapipe/`).
- Older community notes cover running MediaPipe on GPU EC2 instances or Colab + WebRTC streaming.
- Django + MediaPipe demos with Docker/cloud registry support exist (e.g., older MIT Media Lab style projects).
- Browser/web samples can be hosted as static sites (everything still runs client-side).

### Quick Start Tips for Self-Hosting

- **Simple Python:** `pip install mediapipe` then use the Tasks API (PoseLandmarker, HandLandmarker, GestureRecognizer, etc.).
- **Docker:** Use the official MediaPipe Dockerfiles or project-specific compose files (StreamPoseML, DeskPulse, OVMS).
- **Raspberry Pi:** Prefer 64-bit OS, Python 3.9–3.12; build or use pre-built aarch64 wheels when needed. DeskPulse has a one-line installer.
- **Production serving:** Prefer OVMS for exposing graphs over the network with proper model management and streaming.

### Additional Resources

- Curated list: `mgyong/awesome-mediapipe` (desktop, Android, Unity, cloud snippets, etc.)
- Community Slack and Discuss forums linked from the main MediaPipe repo.

*(95 sources cited in original chat)*

---

## Q2: What about media and mediapipe like say music among others

MediaPipe and media (especially music/audio) centers on two main areas: its native Audio Classifier task, and the much larger ecosystem of vision-driven music/interactive audio projects that use hand/pose tracking to control or generate sound.

### 1. Official MediaPipe Audio Capabilities

MediaPipe Tasks includes an Audio Classifier that classifies audio clips or live streams into categories (e.g., "Music", "Speech", guitar, bird song, train whistle, etc.).

- Uses models like YAMNet (trained on AudioSet).
- Supports Python, Android, Web, and Raspberry Pi.
- Can run on continuous microphone streams or audio files.
- Official samples: Raspberry Pi example in mediapipe-samples; Android, Python, and Web guides on the Google AI Edge site; browser demos available via MediaPipe Studio.

This is useful for self-hosted sound-event detection, music vs. speech detection, or environmental audio monitoring on edge devices (including RPi with a USB mic).

### 2. Gesture / Pose → Music & Interactive Audio Projects (Most Active Area)

| Project | What it does | Tech stack | Notes |
|---|---|---|---|
| Music control with hand gestures | Play / pause / stop / resume music via gestures (thumbs up/down, fist, palm, etc.) | MediaPipe Hands + TensorFlow classifier + OpenCV + pygame | Simple, single-script, easy to extend. `jambhaleAnuj/Music-control-with-hand-gesture-recognition` |
| GestureCap Demo | Real-time hand + full-body pose → sound generation (low latency ~25–35 ms) | MediaPipe Hands + Pose | Research-oriented, good for music–movement interaction. `Pranav-0440/gesturecap-demo` |
| Arpeggiator / Hand-controlled synth | One hand controls arpeggios/pitch/volume, other controls drums; audio-reactive visuals | MediaPipe + Tone.js + Three.js (browser) | Fully client-side web app. `collidingScopes/arpeggiator` |
| Gesture Synth / GestureSynth | Hands → chords, melodies, drums, expression (e.g., Titanic theme demo) | MediaPipe Hand Landmarker + Tone.js / Web Audio + Three.js | Browser-based instruments. Multiple variants exist. |
| MidiHands | Fingers map to MIDI chords (C major / A minor scale); works with any DAW | MediaPipe + pygame.midi + OpenCV | Sends real MIDI; good for production use. |
| Handify | Gesture-controlled Spotify player | MediaPipe Hand Landmarker + Spotify Web API | Docker support available. |
| Moosic / FaceMood Music Player | Facial emotion (or face landmarks) → music recommendation / playback | MediaPipe Face + emotion model | Emotion-driven music selection. |
| Gesture DJ | Hand gestures control AI music generation parameters (density, brightness, etc.) in real time | MediaPipe Gesture Recognizer + Google Lyria RealTime | More cloud-oriented (generative AI backend). |
| GSoC-style motion-capture music frameworks | Markerless body/hand pose → music generation, OSC/Jack output to Max/MSP or Pure Data | MediaPipe + custom mapping | Aimed at professional electronic music tools. |

Other common patterns: air instruments / virtual string plucking with finger tracking; pose-based musical timing detection (start/end of performance phrases); dance or full-body movement → continuous music generation (Gesture2Music-style research systems).

### 3. Self-Hosted / Edge Deployment Notes

- Most gesture-to-music projects run locally with just a webcam + Python or a browser (no cloud required).
- Audio Classifier works well on Raspberry Pi (official sample exists).
- For production-style serving of audio classification or custom graphs, OpenVINO Model Server gives network endpoints.
- Pure media servers (Music Assistant, Mopidy, Navidrome, SoundTime, etc.) are separate from MediaPipe but combinable with the gesture projects above for hands-free control.

### Quick Starting Points

- Audio classification only → Official MediaPipe Audio Classifier + YAMNet (Python or RPi sample).
- Gesture music control → the hand-gesture music player repos or the browser Tone.js arpeggiators (easiest to try immediately).
- More advanced synthesis → MidiHands or the various GestureSynth projects.

*(40 sources cited in original chat)*

---

## Q3: Oh provide links to everything you mentioned

Full link list for the official MediaPipe audio docs/samples plus every gesture-to-music/emotion-to-music repo and supporting MediaPipe repo/docs link named above. This list was later deduplicated and categorized into `01_REFERENCES.md` sections 1–2, which is the canonical version to use.

---

## Q4: Mediapipe has a huge use case it seems

Yes — MediaPipe has an unusually broad and practical set of use cases for an open-source ML framework.

### Core Strengths That Drive Adoption

- **Real-time, on-device performance:** designed for live video/audio streams with low latency, running efficiently on phones, browsers, Raspberry Pi, desktops, and edge devices.
- **Cross-platform:** Android, iOS, Web (JS/WASM + WebGPU), Python, C++, and more.
- **Ready-to-use high-quality models + customization:** pre-built solutions (pose, hands, face mesh, gestures, object detection, segmentation, audio classification), plus Model Maker for fine-tuning.
- **Privacy-friendly:** everything can run fully locally — no cloud required for inference.

### Major Use-Case Categories

1. **Human Understanding** (biggest cluster) — pose estimation & activity recognition (fitness, sports analytics, physical therapy, fall detection, yoga/dance feedback); hand tracking & gesture recognition (touchless interfaces, sign language, virtual instruments, AR controls, accessibility); face mesh/landmarks/expression (AR filters, avatars, emotion detection, driver monitoring, try-on apps); holistic (face + hands + pose combined).
2. **Interactive Media & Creative Tools** — gesture-controlled music/instruments, motion-to-sound/dance visualization, virtual cameras/background replacement, AR effects and real-time filters.
3. **Audio** — sound event classification, real-time audio analysis on edge devices.
4. **Accessibility & Healthcare** — hands-free computer control, rehabilitation/movement analysis, assistive communication systems.
5. **Retail, Automotive & Industrial** — virtual try-on, driver monitoring/drowsiness detection, gesture-based machine control, quality inspection.
6. **Education, Research & Prototyping** — rapid prototyping of multimodal AI demos, academic CV/HCI/music-tech/biomechanics research, teaching real-time ML pipelines.
7. **Emerging / Generative** — integration points with on-device LLMs and other generative models (Google AI Edge / LiteRT), multimodal vision+audio+text pipelines.

Because the framework is open-source (Apache 2.0), modular, and well-documented, it's used both by hobbyists and companies shipping production features — almost any application that needs to understand people or media in real time can plug in a MediaPipe solution with relatively little effort.

---

## Q5: Lets say media pipe computer controll similar to iron mans computer

Yes — MediaPipe is excellent for Iron Man / JARVIS-style computer control. You can build (or run existing) systems that let you control the mouse, keyboard, volume, media, windows, and even 3D holographic UIs using only hand gestures from a webcam. Everything runs locally.

### 1. Practical Desktop Control (Virtual Mouse + Keyboard)

| Project | Key Features | Link |
|---|---|---|
| GestureMouse / hand-gesture-pc-control | Cursor move, click, right-click, scroll, drag, on-screen keyboard, Alt+Tab. Cross-platform. | `ArdaGral06/hand-gesture-pc-control` |
| Gesture Control (plugin architecture) | Highly extensible. System navigation, media controls, volume, custom plugins. | `oleg-putseiko/gesture-control` |
| GestureX | Polished Windows app: mouse, click, scroll, volume. 60 FPS, low latency. | `gesturex.app` |
| AirGestureMouse | Index-finger cursor + pinch clicks + scroll + pause. Clean package. | `songs66/AirGestureMouse` |
| Gesture-Controlled Virtual Mouse | Mouse + voice commands combo. | `Viral-Doshi/Gesture-Controlled-Virtual-Mouse` |
| Hands Gestures Virtual Mouse and Keyboard | Separate or combined mouse + virtual keyboard. | `Eng-Elias/Hands_Gestures_Virtual_Mouse_and_Keyboard` |
| GestureHud | Transparent HUD overlay + mouse control (Windows). | `Sid-V5/GestureHud` |
| Vision Mouse | Fully offline Windows executable, system-tray, global hotkey toggle. | `Ns81000/Vision-Mouse` |

Most use MediaPipe Hands (21 landmarks) + PyAutoGUI / pynput for OS control.

### 2. Iron Man / JARVIS Aesthetic & Holographic Interfaces

| Project | Description | Link |
|---|---|---|
| Gesture Lab | High-fidelity Iron Man armor workshop, holographic environment, pinch/assemble gestures. Three.js + MediaPipe. | `quiet-node/gesture-lab` |
| JARVIS MARK XI AR HUD | Browser-based AR HUD with real-time hand tracking, pinch-to-grab 3D objects, glassmorphism UI. | `vinayak-hariharno/Jarvis-Mark-XI-AR-Hud` |
| Iron Interface | 3D particle visualizations controlled by hand gestures + voice ("Jarvis, change to a sphere"). | `collidingScopes/iron-interface` |
| JARVIS Holographic | Full HUD with Earth/terrain control, panels, sound effects, LLM integration. | `xxjun9527/jarvis-holographic` |
| Tony Stark Hand Control | Multi-camera accessibility-focused control + experimental 3D room mapping. | `Capslockb/tony-stark-hand-control` |
| Jarvis 3D Gesture Control | Browser SPA for controlling 3D models with hands. | Search `RmaNMetaverse/Jarvis-3D-GestureControl` or related demos |

### 3. How These Systems Work (Typical Pipeline)

1. Webcam → OpenCV frame capture
2. MediaPipe Hands (or Gesture Recognizer) → 21 3D landmarks
3. Gesture logic (pinch = click, index finger = cursor, fist = drag, V-sign = scroll, etc.)
4. Smoothing filters (1-Euro filter is common) to reduce jitter
5. PyAutoGUI / pynput / Win32 → actual mouse/keyboard events
6. Optional: transparent HUD overlay, voice (for full JARVIS), Three.js for 3D holograms

### Quick Recommendations

- Just want working mouse control today → `ArdaGral06/hand-gesture-pc-control` or GestureX.
- Want the full Iron Man vibe → Gesture Lab or JARVIS MARK XI.
- Accessibility / production-ish → Vision Mouse or Tony Stark Hand Control.
- Build your own → MediaPipe Hands + a few dozen lines of PyAutoGUI is surprisingly effective.

*(42 sources cited in original chat)*

---

## Q6: Cause maybe I can create a jarvis interface over my screens and the cam can track where and what I do and work with that xD so llm integration would be awesome

Yes — that's a very doable and fun project. A JARVIS-style system that sits over your screens, watches you via webcam (hands, pose, face), and talks/acts through an LLM is completely realistic with current open-source tools.

### High-Level Architecture

```
Webcam → MediaPipe (Hands + Face + Pose)
         ↓
Gesture / Gaze / Attention Detector
         ↓
Overlay HUD (transparent window across monitors)
         ↓
LLM Agent (local or cloud) ←→ Tools (mouse/keyboard, apps, search, smart home, etc.)
         ↓
Voice (TTS) + Visual feedback on the HUD
```

### Recommended Building Blocks

**1. Vision Layer (MediaPipe)** — hand tracking (cursor, clicks, pinches, swipes, "select this window"); face mesh/gaze approximation (where you're looking); pose (optional — posture, "I'm pointing at the left monitor").

**2. Overlay / HUD** — transparent always-on-top window(s) spanning one or multiple monitors. Technologies: Electron/Tauri, Python + PyQt/Dear PyGui/pygame with transparent flags, or web tech (Three.js/React) in a transparent Chromium window. Shows hand skeleton, current mode, LLM status, floating panels, reticle where you're pointing.

**3. LLM Integration ("the JARVIS brain")**

| Option | Strengths | Notes |
|---|---|---|
| Ollama + Open WebUI / LibreChat | Easiest local setup | Run Llama 3.1/3.2, Qwen, Mistral, Phi-4, etc. |
| LM Studio | Great GUI + OpenAI-compatible API | Very beginner-friendly |
| vLLM / text-generation-webui | High performance | Good if you have a decent GPU |
| Continue.dev / Aider / Open Interpreter | Already agent-oriented | Can control your computer |
| Cloud (Claude / GPT-4o / Gemini) | Strongest reasoning | Use via API if you don't mind cloud |

You can expose the LLM as an OpenAI-compatible endpoint so the rest of your system talks to it the same way.

**4. Agent / Tool Layer** — mouse & keyboard control (via MediaPipe gestures or LLM tool calls); open apps, switch windows, control volume/media; search the web, control smart home (Home Assistant), manage calendar, etc.; "look at what I'm pointing at and explain it" (screen capture + vision model). Tools like Open Interpreter, Continue, or a simple LangChain/LlamaIndex agent work well here.

### Existing Projects That Get You Part of the Way

- Gesture Lab and JARVIS MARK XI → already have holographic/HUD + MediaPipe hand control
- Tony Stark Hand Control and GestureHud → solid tracking + desktop control foundations
- Open Interpreter or Aider → LLM that can already control your computer
- Combine any of the strong virtual-mouse projects (GestureMouse, GestureX, etc.) with an LLM agent

### Suggested Development Path

1. **Phase 1 – Tracking + Overlay:** MediaPipe hands working + transparent multi-monitor HUD showing skeleton and reticle.
2. **Phase 2 – Basic Control:** map gestures to mouse/keyboard.
3. **Phase 3 – LLM Connection:** voice input (Whisper/local STT) + TTS, connect to a local LLM via OpenAI-compatible API.
4. **Phase 4 – True Agent:** give the LLM tools ("click where I'm pointing", "summarize the window I'm looking at", "open Spotify and play X").
5. **Polish:** mode switching (Idle/Control/Chat/Presentation), confidence thresholds, smoothing, multi-monitor awareness, optional face recognition so it only responds to you.

### Extra Cool Ideas

- Point at a window → LLM reads/summarizes it
- "Jarvis, rearrange my windows" while gesturing
- Context awareness: knows which monitor/app has focus
- Combine with screen capture + vision-language model (LLaVA, Qwen-VL, GPT-4o) so it can see what you're pointing at
- Local-only mode for privacy + optional cloud fallback for harder reasoning

---

## Q7: And another layer implement a method to throw stuff from tablet to pc via gestures

Yes — "throwing" files/content from tablet → PC (or vice versa) with gestures is a perfect extra layer for your JARVIS system.

### Existing Gesture "Throw / Catch / Drop" Projects

| Project | How it works | Link / Notes |
|---|---|---|
| magic_file_transfer (Fadlan Send) | On phone: select file → clench fist → open hand → file appears on laptop. Uses MediaPipe on the receiving side. | `MAliffadlan/magic_file_transfer` |
| Gesture Drop | Explicitly inspired by Huawei's gesture transfer. Grab / mark / throw / drop between two PCs on LAN. | `sachinlodhi/gesture_drop` |
| AirShare / similar hackathon projects | MediaPipe + OpenCV for grab/throw gestures + WebSocket/Wi-Fi Direct transfer between laptop ↔ mobile. | Several variants on Devpost/GitHub (search "AirShare MediaPipe") |
| Academic / paper implementations | "Catch" + "Throw" gestures over Bluetooth PAN or LAN between nearby PCs. | Described in recent papers using MediaPipe Hands |

Huawei also demoed a commercial palm→fist "grab" then throw-to-another-device feature, so the interaction pattern is proven.

### Recommended Architecture

1. **Reliable transfer backend** — LocalSend (best overall open-source AirDrop alternative: Windows, macOS, Linux, Android, iOS; encrypted, fast, no cloud). Alternatives: PairDrop, Snapdrop forks, or a custom WebSocket/HTTP server.
2. **Gesture layer on the PC (MediaPipe)** — detect a clear "throw" motion (fist → open hand + forward velocity, or a flick toward a specific screen/zone); optionally detect direction so it knows "to tablet" vs "to another PC".
3. **Tablet side** — companion app or just LocalSend running; optional lightweight gesture detector, or a "ready to receive" state when the PC signals it.
4. **Integration into the JARVIS HUD** — flying icon/particle effect from your hand toward the target device when throwing; LLM can confirm ("Received photo from tablet" or "Throw this PDF to the tablet?").

### Simple Implementation Path

- **Phase 1 – Working transfer:** install LocalSend on PC + tablet, get comfortable with normal send/receive.
- **Phase 2 – Gesture trigger:** MediaPipe Hands on PC detects a reliable throw gesture (fist/open-hand + velocity); on trigger, call LocalSend's API/CLI/automation to send the currently selected file or clipboard.
- **Phase 3 – Bidirectional + polish:** "catch" gesture on PC to accept incoming; visual feedback on the HUD; optional LLM voice confirmation.
- **Phase 4 – Smarter selection:** point at a window/file on the PC → "throw this", or select on tablet and throw toward the PC camera.

### Extra Nice Touches

- Multi-monitor awareness: throw toward left/right screen zone
- Content-type awareness (image → open in viewer, text → paste, etc.)
- LLM agent integration: "Jarvis, throw the latest screenshot to the tablet"

*(40 sources cited in original chat)*

---

## Q8: Provide complete outline of my idea

*(This is the final synthesis — see `README.md` and `02_PROJECT_PLAN.md` through `06_DECISIONS.md`, which were derived directly from this outline.)*

### 1. Core Vision

A fully local-first (or hybrid) Iron Man/JARVIS-inspired system that overlays a smart HUD across PC monitors, uses a webcam + MediaPipe to continuously track hands/pose/face/gaze, lets you control the computer and talk to an intelligent agent purely through gestures + voice, seamlessly moves files/screenshots/text between tablet and PC via "throw/catch/drop" gestures, and feels cinematic, responsive, and private.

### 2. Main Layers / Modules

- **A. Perception Layer (MediaPipe):** Hand Landmarker/Gesture Recognizer (21 landmarks, pinches, fists, open palms, flicks, swipes, pointing); optional Pose + Face Landmarker; runs on PC webcam (primary), optional tablet tracking; outputs positions/velocity/gesture labels/pointing direction/confidence; 1-Euro smoothing.
- **B. Interaction & Control Layer:** virtual mouse & keyboard, window/app control, media & volume control, mode switching (Idle/Control/Chat/Transfer/Presentation), multi-monitor awareness.
- **C. HUD / Overlay Layer:** transparent always-on-top windows across monitors; hand skeleton/reticle, mode & status, floating panels, particle/flying-icon throw effects, LLM response bubbles/transcripts; Electron/Tauri/PyQt/web tech (Three.js/React) in transparent Chromium.
- **D. Intelligence Layer (LLM Agent):** local LLM (Ollama/LM Studio/vLLM) or cloud API; voice input (Whisper/local STT) + TTS; tool-using agent (mouse/keyboard control, open apps, rearrange windows, summarize what you're pointing at via screen capture + vision model, manage files/calendar/smart home/web search, confirm/execute transfers); context awareness (focused window, recent gestures, connected devices).
- **E. Cross-Device Transfer Layer ("Throw/Catch"):** gesture-triggered movement between tablet ↔ PC (select → grab/fist → throw/flick toward target → catch/open-hand or auto-accept → transfer with visual feedback); backend: LocalSend preferred, or custom WebSocket/HTTP, PairDrop, pure P2P; bidirectional and multi-device ready.
- **F. System & Infrastructure Layer:** device discovery (mDNS/LocalSend discovery); configuration & calibration (gesture sensitivity, monitor layout, camera position); privacy controls (local-only mode, camera kill switch, LAN-only by default); logging, profiles, hotkey/voice overrides; optional Home Assistant/smart-home integration, multi-user later.

### 3. Typical User Flows

1. **Everyday Control:** point → cursor moves; pinch → click; "Jarvis, open the project folder" → agent acts.
2. **Content Throw (Tablet → PC):** select photo on tablet → grab → throw toward PC camera → HUD shows incoming object → lands on desktop/opens automatically; optional voice confirmation.
3. **PC → Tablet:** point at a window/file → "throw this to tablet" (gesture or voice) → tablet receives it.
4. **Intelligent Assistance:** point at a code window → "Explain this function" → LLM answers with overlay; "Summarize everything I'm looking at" → agent uses screen + vision.
5. **Mode Changes:** gesture or voice command switches between pure control, chat, transfer-ready, or presentation mode.

### 4. Technology Stack Recommendation

| Layer | Suggested Technologies |
|---|---|
| Vision | MediaPipe Tasks (Hands, Gesture, Pose, Face) |
| Desktop Control | PyAutoGUI / pynput / platform-specific APIs |
| Overlay / HUD | Electron / Tauri or Python (PyQt / Dear PyGui) + web frontend |
| LLM & Agent | Ollama + Open WebUI / Continue / Open Interpreter + tool calling |
| Voice | Faster-Whisper + Piper / Coqui TTS (or cloud) |
| File Transfer | LocalSend (primary) + custom trigger API |
| Networking | Local network only (mDNS, WebSocket, HTTP) |
| Language | Python (core) + TypeScript/JavaScript (HUD) |

### 5. Development Phases (Suggested Roadmap)

- **Phase 1 – Foundation:** MediaPipe hands + basic virtual mouse + simple transparent overlay.
- **Phase 2 – Solid Control:** full gesture set, multi-monitor support, smoothing, mode system.
- **Phase 3 – Intelligence:** local LLM + voice + basic agent tools.
- **Phase 4 – Throw / Catch:** integrate LocalSend + reliable throw/catch gestures + visual effects.
- **Phase 5 – Polish & Magic:** HUD refinements, context awareness, "what am I pointing at", multi-device robustness, JARVIS personality/voice.
- **Phase 6 – Advanced:** gaze estimation, dual-hand interactions, tablet-side companion app, plugin system.

### 6. Key Principles

- Local-first and private by default
- Low latency (target < 50–80 ms for gestures)
- Graceful degradation (works even if LLM or tablet is offline)
- Highly configurable gestures and sensitivity
- Cinematic but actually useful day-to-day

---

*Source: "MediaPipe Self-Hosted Edge Projects" — Grok chat. Pasted and preserved here as the origin document for this project; see `01_REFERENCES.md` through `14_STARTER_COMBO.md` for the distilled/actionable planning docs built from it.*
