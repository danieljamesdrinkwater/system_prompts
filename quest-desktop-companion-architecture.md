# Quest Desktop Companion App - Architecture

A Meta Quest standalone app that mirrors your desktop into VR with hand tracking
for point/click/right-click and dictation for text input.

---

## System Overview

```
+---------------------------+          Wi-Fi 6E          +---------------------------+
|     META QUEST 3          |  <======================>  |     HOST COMPUTER         |
|                           |                            |                           |
|  +---------------------+  |    encoded video stream    |  +---------------------+  |
|  | OpenXR Renderer      |  |  <---------------------  |  | Screen Capture       |  |
|  | - quad layer desktop |  |                            |  | - DXGI (Win)         |  |
|  | - hand ray overlay   |  |    mouse/keyboard cmds    |  | - PipeWire (Linux)   |  |
|  +---------------------+  |  --------------------->   |  | - ScreenCaptureKit   |  |
|                           |                            |  +---------------------+  |
|  +---------------------+  |    audio stream (opus)     |                           |
|  | Hand Tracking        |  |  <---------------------  |  +---------------------+  |
|  | - ray cast to screen |  |                            |  | Hardware Encoder     |  |
|  | - pinch = click      |  |    voice text (json)      |  | - NVENC / AMF /      |  |
|  | - gestures           |  |  --------------------->   |  |   VAAPI              |  |
|  +---------------------+  |                            |  +---------------------+  |
|                           |    control channel (tcp)   |                           |
|  +---------------------+  |  <======================>  |  +---------------------+  |
|  | Voice / Dictation    |  |                            |  | Input Injector       |  |
|  | - Meta Voice SDK     |  |                            |  | - SendInput (Win)    |  |
|  | - whisper.cpp local  |  |                            |  | - uinput (Linux)     |  |
|  +---------------------+  |                            |  | - CGEvent (macOS)    |  |
+---------------------------+                            |  +---------------------+  |
                                                         +---------------------------+
```

Two executables:
1. **Quest App** (APK) - VR renderer, hand tracking, voice input
2. **Desktop Server** (companion daemon) - screen capture, encoding, input injection

---

## Component 1: Quest App (VR Client)

### Platform & SDK

| Choice           | Detail                                                    |
|------------------|-----------------------------------------------------------|
| Engine           | **Unity 6** (6000.x) with Meta XR All-in-One SDK v85+    |
| XR Plugin        | `com.unity.xr.meta-openxr` (replaces legacy Oculus plugin)|
| Hand Tracking    | Meta XR Interaction SDK (ray + poke interactors)          |
| Voice            | Meta Voice SDK (`com.meta.xr.sdk.voice`) + whisper.cpp    |
| Video Decode     | Android `MediaCodec` (hardware H.265/AV1 decode)         |
| Target           | Quest 3 / Quest 3S / Quest Pro (Android API 32+)         |

**Alternative path**: Native OpenXR + Android NDK (C/C++) for maximum control
over the decode pipeline. More work but lower latency. Use `meta-quest/Meta-OpenXR-SDK`
from GitHub with CMake 3.22+ and NDK r27+.

### Virtual Desktop Rendering

The desktop is rendered as an **OpenXR quad composition layer** positioned in
front of the user in VR space.

```
Scene Layout (top-down view):

          [user head]
              |
              | 1.5m
              |
     +--------+--------+
     |                  |
     |  Virtual Screen  |   ~2.5m wide (adjustable)
     |  (quad layer)    |   aspect ratio matches desktop
     |                  |
     +------------------+

     Optional: curved cylinder layer for ultrawide
```

- Decode each video frame via `MediaCodec` into an `ExternalTexture`
- Bind that texture to the quad layer each frame
- Support resizing/repositioning the virtual screen via grab gestures
- Optional: multi-monitor = multiple quad layers side by side

### Hand Tracking -> Mouse Input

```
Hand Tracking Pipeline:

1. OVRHand.PointerPose  ->  Ray origin + direction
2. Physics.Raycast against virtual screen plane  ->  hit point (world space)
3. Transform hit point to screen UV (0-1, 0-1)
4. Map UV to desktop pixel coords:
     pixel_x = uv.x * screen_width
     pixel_y = (1 - uv.y) * screen_height
5. Send (pixel_x, pixel_y) to desktop server as mouse_move

Gesture Detection:
- Index pinch  (GetFingerIsPinching(Index))     -> LEFT CLICK
- Index pinch hold + hand move                  -> DRAG
- Middle pinch (GetFingerIsPinching(Middle))     -> RIGHT CLICK
- Pinch release                                 -> MOUSE UP
- Thumb+index quick double pinch                -> DOUBLE CLICK
- Scroll: open palm tilt forward/back           -> SCROLL UP/DOWN
```

**Pinch detection API**:
```csharp
// Unity C# pseudocode
OVRHand hand = rightHand.GetComponent<OVRHand>();

bool leftClick = hand.GetFingerIsPinching(OVRHand.HandFinger.Index);
bool rightClick = hand.GetFingerIsPinching(OVRHand.HandFinger.Middle);
float pinchStrength = hand.GetFingerPinchStrength(OVRHand.HandFinger.Index);

// Use PointerPose for stable ray direction (filtered by runtime)
if (hand.IsPointerPoseValid) {
    Transform pointer = hand.PointerPose;
    Ray ray = new Ray(pointer.position, pointer.forward);
    // Raycast against desktop quad...
}
```

**Direct touch (poke) mode**: When the hand is close to the virtual screen
(<15cm), switch from ray mode to poke mode. Track index fingertip joint
position relative to the screen plane. Contact = click.

### Voice / Dictation

**Primary: Meta Voice SDK (cloud, via Wit.ai)**
- Activate dictation on a trigger gesture (e.g., thumb+pinky pinch)
- Audio is streamed to Wit.ai, transcription returned in real-time
- Transcribed text sent to desktop server as keystroke sequence
- Requires internet — fine for most home setups
- Free to use, no API key costs

**Fallback: whisper.cpp (on-device)**
- Bundle `whisper-tiny` or `whisper-base` GGML model (~75MB / ~150MB)
- Use `whisper-meta-quest` Unity bindings
- Higher latency (~2-5s per utterance), may cause frame drops
- Fully offline / private

**Dictation flow**:
```
1. User makes activation gesture (thumb+pinky pinch)
2. Visual indicator appears: "Listening..."
3. Audio captured from Quest microphone
4. Sent to Wit.ai (or local whisper)
5. Transcription received
6. Text displayed floating near hand for confirmation
7. User pinches to confirm -> text sent to desktop as keystrokes
   OR user dismisses with palm-out gesture
```

### Virtual Keyboard (Optional)

For short inputs, render a floating keyboard in VR space that responds to
poke interactions (index finger poking keys). Meta's Interaction SDK has
built-in support for poke-based button interactions.

---

## Component 2: Desktop Server (Companion Daemon)

A lightweight cross-platform application that runs on the host computer.

### Screen Capture

| Platform | API                      | Notes                              |
|----------|--------------------------|------------------------------------|
| Windows  | DXGI Desktop Duplication | GPU-accelerated, ~1ms capture time |
| Linux    | PipeWire + DMA-BUF       | Wayland-native, zero-copy          |
| Linux    | X11 SHM / XComposite     | X11 fallback                       |
| macOS    | ScreenCaptureKit         | Requires macOS 12.3+, low latency  |

Capture target: 60fps at native resolution (or downscaled to 1080p/1440p
for bandwidth).

### Hardware Video Encoding

| GPU Vendor | Encoder API | Codecs              |
|------------|-------------|----------------------|
| NVIDIA     | NVENC       | H.264, HEVC, AV1    |
| AMD        | AMF         | H.264, HEVC, AV1    |
| Intel      | QSV         | H.264, HEVC, AV1    |
| Linux (any)| VAAPI       | H.264, HEVC          |
| macOS      | VideoToolbox| H.264, HEVC          |

**Encoding settings for VR desktop**:
- Codec: HEVC (best quality/bandwidth tradeoff; Quest 3 has hardware decode)
- Bitrate: 30-80 Mbps variable (adjustable)
- Preset: low-latency / tune=zerolatency
- GOP: 1 second, with periodic IDR for recovery
- Slicing: enable for lower per-frame latency

### Network Transport

**Control channel (TCP)**:
```json
// Quest -> Server: mouse events
{"type": "mouse_move", "x": 1024, "y": 768}
{"type": "mouse_down", "button": "left"}
{"type": "mouse_up", "button": "left"}
{"type": "mouse_down", "button": "right"}
{"type": "scroll", "delta": -3}

// Quest -> Server: keyboard events
{"type": "key_press", "key": "a"}
{"type": "key_combo", "keys": ["ctrl", "c"]}
{"type": "text_input", "text": "Hello world"}

// Server -> Quest: status
{"type": "resolution", "width": 2560, "height": 1440}
{"type": "clipboard", "text": "copied text"}
```

**Video channel (UDP)**:
- Custom RTP-like framing or WebRTC media channel
- Forward Error Correction (FEC) for packet loss resilience
- Adaptive bitrate based on network conditions
- Target: < 30ms motion-to-photon latency on Wi-Fi 6E

**Discovery**: UDP broadcast on local network (port 9943, following ALVR
convention) or manual IP entry.

### Input Injection

**Windows** - `SendInput()` API:
```c
// Move mouse to absolute position
INPUT input = {0};
input.type = INPUT_MOUSE;
input.mi.dx = (x * 65535) / screen_width;   // normalized coords
input.mi.dy = (y * 65535) / screen_height;
input.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE;
SendInput(1, &input, sizeof(INPUT));

// Left click
input.mi.dwFlags = MOUSEEVENTF_LEFTDOWN;
SendInput(1, &input, sizeof(INPUT));
input.mi.dwFlags = MOUSEEVENTF_LEFTUP;
SendInput(1, &input, sizeof(INPUT));
```

**Linux** - uinput:
```python
import evdev
from evdev import UInput, ecodes

ui = UInput({
    ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y],
    ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
})

# Move mouse
ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
ui.syn()

# Click
ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)  # down
ui.syn()
ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)  # up
ui.syn()
```

**macOS** - Core Graphics:
```swift
// Move mouse
let moveEvent = CGEvent(
    mouseEventSource: nil,
    mouseType: .mouseMoved,
    mouseCursorPosition: CGPoint(x: x, y: y),
    mouseButton: .left
)
moveEvent?.post(tap: .cghidEventTap)

// Left click
let downEvent = CGEvent(mouseEventSource: nil,
    mouseType: .leftMouseDown, ...)
let upEvent = CGEvent(mouseEventSource: nil,
    mouseType: .leftMouseUp, ...)
```

---

## Implementation Language & Stack

### Recommended: Rust Desktop Server + Unity Quest Client

| Component       | Language | Rationale                                     |
|-----------------|----------|-----------------------------------------------|
| Quest VR App    | C# (Unity) | Best Meta SDK support, fastest iteration    |
| Desktop Server  | Rust     | Cross-platform, safe, excellent for networking and low-level APIs. ALVR is written in Rust. |
| Protocol        | JSON over TCP (control) + raw UDP (video) | Simple, debuggable |

**Alternative**: Python desktop server for rapid prototyping (using
`mss` for screen capture, `pyautogui` for input, `ffmpeg` subprocess
for encoding). Rewrite performance-critical parts in Rust/C++ later.

---

## Project Structure

```
quest-desktop-companion/
├── quest-app/                    # Unity project (Quest APK)
│   ├── Assets/
│   │   ├── Scripts/
│   │   │   ├── DesktopRenderer.cs       # Quad layer + texture decode
│   │   │   ├── HandInputManager.cs      # Hand tracking -> mouse mapping
│   │   │   ├── VoiceInputManager.cs     # Dictation integration
│   │   │   ├── NetworkClient.cs         # TCP control + UDP video receive
│   │   │   ├── GestureRecognizer.cs     # Pinch, scroll, drag detection
│   │   │   └── ScreenPositioner.cs      # Virtual screen placement/resize
│   │   ├── Prefabs/
│   │   │   ├── VirtualDesktop.prefab
│   │   │   ├── HandCursor.prefab
│   │   │   └── DictationUI.prefab
│   │   └── Plugins/
│   │       └── whisper/                 # whisper.cpp native plugin (fallback STT)
│   ├── Packages/
│   │   └── manifest.json               # Meta XR SDK, Voice SDK, OpenXR plugin
│   └── ProjectSettings/
│       └── OVRManager settings          # Hand tracking enabled
│
├── desktop-server/               # Rust project (companion daemon)
│   ├── src/
│   │   ├── main.rs                      # Entry point, config, discovery
│   │   ├── capture/
│   │   │   ├── mod.rs
│   │   │   ├── windows.rs               # DXGI Desktop Duplication
│   │   │   ├── linux.rs                 # PipeWire / X11
│   │   │   └── macos.rs                 # ScreenCaptureKit
│   │   ├── encode/
│   │   │   ├── mod.rs
│   │   │   └── hardware.rs              # NVENC / AMF / VAAPI / VideoToolbox
│   │   ├── network/
│   │   │   ├── mod.rs
│   │   │   ├── tcp_control.rs           # JSON command channel
│   │   │   ├── udp_video.rs             # Video stream + FEC
│   │   │   └── discovery.rs             # UDP broadcast for auto-connect
│   │   ├── input/
│   │   │   ├── mod.rs
│   │   │   ├── windows.rs               # SendInput
│   │   │   ├── linux.rs                 # uinput / evdev
│   │   │   └── macos.rs                 # CGEvent
│   │   └── audio/
│   │       ├── mod.rs
│   │       └── capture.rs               # System audio capture + Opus encode
│   └── Cargo.toml
│
├── protocol/                     # Shared protocol definitions
│   ├── messages.json                    # JSON schema for control messages
│   └── README.md
│
└── README.md
```

---

## Development Phases

### Phase 1: Proof of Concept (2-4 weeks)
- [ ] Desktop server: screen capture + JPEG encoding + TCP streaming (no hardware encode yet)
- [ ] Quest app: receive JPEG frames over TCP, display on quad
- [ ] Basic hand tracking: ray cast to screen, index pinch = click
- [ ] Send mouse click events back to server, inject with SendInput/uinput
- **Goal**: See your desktop in VR and click on things with your hand

### Phase 2: Low-Latency Video (2-3 weeks)
- [ ] Replace JPEG with hardware H.265 encoding (NVENC/AMF)
- [ ] Switch to UDP transport with packet framing
- [ ] Hardware decode on Quest via MediaCodec
- [ ] Add adaptive bitrate based on network stats
- **Goal**: Smooth, usable desktop at 60fps with < 40ms latency

### Phase 3: Full Input (1-2 weeks)
- [ ] Right click (middle finger pinch)
- [ ] Drag and drop (pinch hold + move)
- [ ] Scroll (palm tilt or two-finger pinch drag)
- [ ] Double click (quick double pinch)
- [ ] Keyboard shortcuts via gesture menu or voice commands
- **Goal**: Full mouse replacement via hand tracking

### Phase 4: Voice / Dictation (1-2 weeks)
- [ ] Integrate Meta Voice SDK for cloud dictation
- [ ] Activation gesture (thumb+pinky pinch)
- [ ] Transcription preview floating near hand
- [ ] Confirm/dismiss gestures
- [ ] Send confirmed text as keystrokes to desktop
- [ ] Integrate whisper.cpp as offline fallback
- **Goal**: Type by speaking

### Phase 5: Polish (2-3 weeks)
- [ ] Multi-monitor support (multiple quad layers)
- [ ] Desktop audio streaming (Opus encoded)
- [ ] Clipboard sync (copy on desktop, paste in VR and vice versa)
- [ ] Screen repositioning and resizing via grab gesture
- [ ] Curved screen option (cylinder layer)
- [ ] System tray icon / menu bar icon for desktop server
- [ ] Auto-discovery (no manual IP entry)
- [ ] Settings panel in VR (resolution, bitrate, screen distance)
- **Goal**: Daily-driver quality

### Phase 6: Platform Support (ongoing)
- [ ] Windows desktop server
- [ ] Linux desktop server (PipeWire + VAAPI)
- [ ] macOS desktop server (ScreenCaptureKit + VideoToolbox)

---

## Open Source References

**Key finding: No open-source Quest-native desktop viewer exists today.** All
existing projects are either PCVR game streamers (ALVR, WiVRn) or PC-side
overlays/compositors (wlx-overlay-s, Simula). This app would fill a real gap.

| Project | Repo | Lang | Stars | Status | Hand Tracking | Useful For |
|---------|------|------|-------|--------|---------------|------------|
| **ALVR** | [alvr-org/ALVR](https://github.com/alvr-org/ALVR) | Rust/C++ | ~7.5k | Active (Apr 2026) | Yes (gesture mapping) | Video pipeline, UDP protocol, encoding, Quest client architecture |
| **WiVRn** | [WiVRn/WiVRn](https://github.com/WiVRn/WiVRn) | C++ | ~1.3k | Active (Feb 2026) | Yes | OpenXR streaming with hand tracking, available on Meta Store |
| **wlx-overlay-s** | [galister/wlx-overlay-s](https://github.com/galister/wlx-overlay-s) | Rust | ~956 | Active (Feb 2026) | No | Screen capture + interactive overlay input patterns (Wayland/X11) |
| **Simula** | [SimulaVR/Simula](https://github.com/SimulaVR/Simula) | Haskell | ~3.2k | Stalled (hw focus) | No | VR window management concepts |
| **Stardust XR** | [StardustXR/server](https://github.com/StardustXR/server) | Rust | ~167 | Active (Dec 2025) | Via Monado | Modular XR display server architecture |
| **FreeRDP** | [FreeRDP/FreeRDP](https://github.com/FreeRDP/FreeRDP) | C | N/A | Active | N/A | Windows host streaming (RDP), has Android JNI bindings |
| **whisper-meta-quest** | [saurabhchalke/whisper-meta-quest](https://github.com/saurabhchalke/whisper-meta-quest) | C++/Unity | N/A | PoC | N/A | On-device Whisper STT on Quest 3 |

### Best references by component:
- **Quest client app architecture**: ALVR + WiVRn (both have Quest Store clients)
- **Screen capture + VR interaction**: wlx-overlay-s (Rust, excellent code quality)
- **Hand tracking patterns**: Meta-OpenXR-SDK samples (`XrHandsFB`, `XrVirtualKeyboard`)
- **Native Quest panels**: Meta Spatial SDK (Kotlin/Android, no game engine needed)

### Meta's Official Samples (on GitHub):
| Repo | What it shows |
|------|---------------|
| `meta-quest/Meta-OpenXR-SDK` | 21 native C samples including hand tracking, virtual keyboard |
| `meta-quest/Meta-Spatial-SDK-Samples` | Native Quest panel apps in Kotlin — relevant for building the desktop viewer without Unity |
| `oculus-samples/Unity-FirstHand` | Hand tracking interaction showcase (Unity/C#) |

---

## Hardware Requirements

**Quest Side**:
- Meta Quest 3 or Quest 3S (Quest 2 possible but weaker hand tracking)
- Wi-Fi 6 minimum, Wi-Fi 6E or 7 recommended (dedicated 5GHz/6GHz band)

**Desktop Side**:
- Any modern GPU with hardware encode (NVIDIA GTX 1650+, AMD RX 5000+, Intel Arc)
- NVIDIA GPUs preferred (NVENC is the most mature and lowest latency)
- Wired ethernet to router recommended (avoids double-wireless hop)

**Network**:
- Dedicated 5GHz or 6GHz Wi-Fi band for Quest (no other heavy traffic)
- Router within line of sight of headset
- 100 Mbps+ available bandwidth between Quest and desktop
