# 01 — Reference Catalog

Every link and resource referenced in the research chat, categorized. Last verified during chat research (95 + 40 + 40 + 42 sources).

> **Provenance:** This research was originally produced in a "Grok" chat titled *"MediaPipe Self-Hosted Edge Projects"* and was pasted into this project for dissection. Links are reproduced as given; verify any link before relying on it, since repo names/owners can change.

## 1. Official MediaPipe Resources

| Resource | Link |
|---|---|
| Core repo (google-ai-edge/mediapipe) — framework + Tasks APIs, Docker builds, RPi/aarch64 wheels | https://github.com/google-ai-edge/mediapipe |
| Official samples repo (mediapipe-samples) | https://github.com/google-ai-edge/mediapipe-samples |
| Web-focused samples (mediapipe-samples-web, fully client-side browser demos) | https://github.com/google-ai-edge/mediapipe-samples-web |
| Docs & Studio — instant demos, Python/JS/Android/iOS setup, Model Maker | https://developers.google.com/edge/mediapipe |
| MediaPipe Studio (browser demos incl. audio) | https://developers.google.com/edge/mediapipe/solutions/studio |
| MediaPipe Tasks Python API docs (incl. audio) | https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/audio |

## 2. Audio / Music & Interactive Media

### Official Audio
| Resource | Link |
|---|---|
| Audio Classifier overview & guides (Python, Android, Web) | https://developers.google.com/edge/mediapipe/solutions/audio/audio_classifier |
| Raspberry Pi Audio Classifier example | https://github.com/google-ai-edge/mediapipe-samples/tree/main/examples/audio_classifier/raspberry_pi |

### Gesture / Pose → Music Projects
| Project | Description | Link |
|---|---|---|
| Music control with hand gesture recognition | Play/pause/stop via gestures; MediaPipe Hands + TensorFlow + pygame | https://github.com/jambhaleAnuj/Music-control-with-hand-gesture-recognition |
| GestureCap Demo | Hand + full-body pose → real-time sound gen (~25–35 ms latency) | https://github.com/Pranav-0440/gesturecap-demo |
| Arpeggiator | Hand-controlled arpeggiator + drum machine + audio-reactive visuals; Tone.js + Three.js | https://github.com/collidingScopes/arpeggiator |
| Gesture Synth | Camera-based instrument — chords, melodies, expression; Web Audio API | https://github.com/ericwei97-cloud/gesture-synth |
| GestureSynth | Dual-hand melody + drums; Tone.js + Three.js | https://github.com/amerob/GestureSynth |
| MidiHands | Fingers → MIDI chords; works with any DAW (pygame.midi) | https://github.com/kaleprabhat24/MidiHands |
| Handify | Gesture-controlled Spotify player; Docker support | https://github.com/chrismuntean/Handify |
| Moosic | Facial emotion detection → music recommendation | https://github.com/khankhushi/Moosic |
| FaceMood Music Player | MediaPipe Face Landmarker + emotion-driven playback | https://github.com/iceman404/facemood_music_player |
| Gesture DJ | Hand gestures control AI music-gen params (Google Lyria RealTime) | https://github.com/mariagorskikh/gesture-dj |

## 3. Self-Hosted / Edge MediaPipe Projects

| Project | Description | Link |
|---|---|---|
| DeskPulse | Privacy-first posture monitoring; systemd service, RPi 4/5 | https://github.com/EmekaOkaforTech/deskpulse |
| StreamPoseML | Real-time video pose classification toolkit + web app; Docker; PyPI `stream-pose-ml` | https://github.com/mrilikecoding/StreamPoseML |
| Self Care Selfies | Headless video analysis → motion metrics CSV (UCSF MSLAB) | https://github.com/UCSF-MSLAB/self_care_selfies |
| GestureSensor | Face + gesture detection → MQTT; Docker-ready | https://github.com/mmcc-xx/gesturesensor |
| SaraKIT Face Analysis | Face detection/landmarks/mesh for RPi 64-bit | https://github.com/SaraEye/SaraKIT (search "SaraKIT face analysis") |
| Official RPi gesture recognizer examples | MediaPipe Tasks on RPi camera | https://github.com/google-ai-edge/mediapipe-samples/tree/main/examples/gesture_recognizer/raspberry_pi |
| awesome-mediapipe | Curated list: desktop, Android, Unity, cloud snippets | https://github.com/mgyong/awesome-mediapipe |

## 4. Production / Server-Side Serving

| Resource | Link |
|---|---|
| OpenVINO Model Server (OVMS) — serve MediaPipe graphs via gRPC/REST, Docker/K8s | https://github.com/openvinotoolkit/model_server |
| OVMS MediaPipe docs | https://github.com/openvinotoolkit/model_server/blob/main/docs/mediapipe.md |
| OVMS MediaPipe demos | https://github.com/openvinotoolkit/model_server/tree/main/demos/mediapipe |

## 5. Iron Man / JARVIS Aesthetic & Holographic UIs

| Project | Description | Link |
|---|---|---|
| Gesture Lab | Iron Man armor workshop, holographic env, pinch/assemble; Three.js + MediaPipe | https://github.com/quiet-node/gesture-lab |
| JARVIS MARK XI AR HUD | Browser AR HUD, real-time hand tracking, pinch-to-grab 3D, glassmorphism | https://github.com/vinayak-hariharno/Jarvis-Mark-XI-AR-Hud |
| Iron Interface | 3D particle visuals controlled by gestures + voice | https://github.com/collidingScopes/iron-interface |
| JARVIS Holographic | HUD with Earth/terrain control, panels, sound, LLM integration | https://github.com/xxjun9527/jarvis-holographic |
| Tony Stark Hand Control | Multi-camera accessibility control + experimental 3D room mapping | https://github.com/Capslockb/tony-stark-hand-control |
| Jarvis 3D Gesture Control | Browser SPA for 3D model control | Search: `RmaNMetaverse/Jarvis-3D-GestureControl` |

## 6. Virtual Mouse / Desktop Control

| Project | Description | Link |
|---|---|---|
| hand-gesture-pc-control | Cursor, click, right-click, scroll, drag, on-screen keyboard, Alt+Tab | https://github.com/ArdaGral06/hand-gesture-pc-control |
| Gesture Control (plugin architecture) | System nav, media, volume, custom plugins | https://github.com/oleg-putseiko/gesture-control |
| GestureX | Polished Windows app: mouse/click/scroll/volume, 60 FPS | https://gesturex.app |
| AirGestureMouse | Index-finger cursor + pinch clicks + scroll + pause | https://github.com/songs66/AirGestureMouse |
| Gesture-Controlled Virtual Mouse | Mouse + voice commands combo | https://github.com/Viral-Doshi/Gesture-Controlled-Virtual-Mouse |
| Hands Gestures Virtual Mouse and Keyboard | Separate or combined mouse + virtual keyboard | https://github.com/Eng-Elias/Hands_Gestures_Virtual_Mouse_and_Keyboard |
| GestureHud | Transparent HUD overlay + mouse control (Windows) | https://github.com/Sid-V5/GestureHud |
| Vision Mouse | Fully offline Windows exe, tray icon, global hotkey | https://github.com/Ns81000/Vision-Mouse |

## 7. Gesture Throw / Catch / Transfer

| Project | Description | Link |
|---|---|---|
| magic_file_transfer (Fadlan Send) | Phone: select file → fist → open hand → file lands on laptop; MediaPipe | https://github.com/MAliffadlan/magic_file_transfer |
| Gesture Drop | Grab/mark/throw/drop between two PCs on LAN (Huawei-inspired) | https://github.com/sachinlodhi/gesture_drop |
| LocalSend (primary backend) | Open-source AirDrop alternative; encrypted, cross-platform | https://localsend.org · https://github.com/localsend/localsend |
| PairDrop | Browser-based self-hostable transfer | https://github.com/schlagmichdoch/PairDrop |
| AirShare variants | Hackathon projects; search "AirShare MediaPipe" on Devpost/GitHub | https://github.com/search?q=AirShare+MediaPipe |

## 8. LLM / Voice / Agent Stack (named in chat)

| Tool | Purpose | Link |
|---|---|---|
| Ollama | Easiest local LLM runtime | https://ollama.com |
| Open WebUI | Local LLM chat UI | https://github.com/open-webui/open-webui |
| LibreChat | Self-hosted AI chat platform | https://github.com/danny-avila/LibreChat |
| LM Studio | GUI + OpenAI-compatible API | https://lmstudio.ai |
| vLLM | High-performance serving | https://github.com/vllm-project/vllm |
| text-generation-webui (oobabooga) | Local LLM web UI | https://github.com/oobabooga/text-generation-webui |
| Continue.dev | AI coding agent (IDE) | https://github.com/continuedev/continue |
| Aider | Terminal AI pair programmer | https://github.com/Aider-AI/aider |
| Open Interpreter | LLM that controls your computer | https://github.com/OpenInterpreter/open-interpreter |
| Faster-Whisper | Local speech-to-text | https://github.com/SYSTRAN/faster-whisper |
| Piper TTS | Local text-to-speech | https://github.com/rhasspy/piper |
| Coqui TTS | Local TTS | https://github.com/coqui-ai/TTS |

## 8b. Pure Media Servers (mentioned alongside music projects)

Separate from MediaPipe, but combinable with gesture control for hands-free playback:

| Server | Role | Link |
|---|---|---|
| Music Assistant | Multi-provider music server (Spotify, local, etc.) | https://github.com/music-assistant |
| Mopidy | Extensible music server (Python, MPD-compatible) | https://github.com/mopidy/mopidy |
| Navidrome | Self-hosted music streamer (Subsonic API) | https://github.com/navidrome/navidrome |
| SoundTime | Media project named in the research chat | ⚠️ not independently verified — search "SoundTime self-hosted" before use |

## 8c. Transfer Backend Alternatives (in addition to LocalSend)

| Tool | Role | Link |
|---|---|---|
| Snapdrop | Browser-based P2P file sharing (LocalSend alternative) | https://github.com/RobinLinus/snapdrop |
| PairDrop | Self-hostable fork/evolution of Snapdrop | https://github.com/schlagmichdoch/PairDrop |

## 8d. MediaPipe Community Channels

| Channel | Notes | Link |
|---|---|---|
| MediaPipe GitHub repo | README links the current community channels (Discord / Discuss) | https://github.com/google-ai-edge/mediapipe |
| MediaPipe community discussions | Official discussion forum (check main repo for the live link) | https://github.com/google-ai-edge/mediapipe/discussions |

## 9. Key Building Blocks Mentioned

| Tool | Role |
|---|---|
| PyAutoGUI | Cross-platform mouse/keyboard control |
| pynput | Low-level input control |
| Tone.js | Web Audio synthesis (browser gestures-to-music) |
| Three.js | 3D / holographic HUD rendering |
| YAMNet | AudioSet classifier model used by Audio Classifier |
| 1-Euro filter | Jitter smoothing for gesture tracking |
| MediaPipe Model Maker | Custom model fine-tuning |
| Home Assistant | Smart-home integration target |

## 10. Follow-up Ideas Not Yet Linked

- LLaVA — open vision-language model (local) | https://github.com/haotian-liu/LLaVA
- Qwen-VL — open vision-language model family (local) | https://github.com/QwenLM/Qwen-VL
- GPT-4o — cloud vision-language model (API) | https://platform.openai.com/docs/guides/vision
- Edgepipes — pure-Python MediaPipe-inspired framework (search "Edgepipes python")
- Gesture2Music — research on full-body movement → music generation (search "Gesture2Music")
- Google Lyria RealTime — generative music API used by Gesture DJ | https://aistudio.google.com/ (Lyria) — verify current access
- MediaPipe Model Maker (customization) | https://developers.google.com/edge/mediapipe/solutions/model_maker
