#!/data/data/com.termux/files/usr/bin/bash
# NOTE: #!/bin/bash also works if this script is sourced rather than executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# setup-voice-assistant.sh - Voice assistant with Anthropic API or Ollama
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${GREEN}===${NC} $* ${GREEN}===${NC}"; }

ASSISTANT_DIR="$HOME/voice-assistant"
VENV_DIR="$HOME/venvs/voice-assistant"
PROFILE_FILE="$HOME/.bashrc"
BOOT_DIR="$HOME/.termux/boot"

# ---- Validate Python -------------------------------------------------------
header "Checking Python installation"

if ! command -v python &>/dev/null; then
    warn "Python not found. Installing via pkg ..."
    if pkg install -y python; then
        info "Python installed."
    else
        error "Failed to install Python. Run setup-base.sh first."
        exit 1
    fi
fi

if python -c "print('ok')" 2>/dev/null | grep -q "ok"; then
    info "Python runtime is functional."
else
    error "Python is installed but runtime test failed."
    exit 1
fi

# ---- Install / upgrade pip -------------------------------------------------
header "Setting up pip"

if python -m pip --version &>/dev/null; then
    info "pip is already available."
else
    warn "pip not found — installing via ensurepip."
    if python -m ensurepip --upgrade; then
        info "pip installed via ensurepip."
    else
        error "Failed to install pip. Try: pkg install python-pip"
        exit 1
    fi
fi

# ---- Install Termux API package ---------------------------------------------
header "Installing Termux API"

if command -v termux-microphone-record &>/dev/null; then
    info "Termux API is already installed."
else
    echo -e "  Installing ${YELLOW}termux-api${NC} ..."
    if pkg install -y termux-api; then
        info "Termux API installed."
    else
        error "Failed to install termux-api."
        warn "Voice recording and TTS require the Termux:API app from F-Droid."
        warn "Install it manually: pkg install termux-api"
    fi
fi

warn "Ensure the Termux:API companion app is installed from F-Droid."
warn "Without it, termux-microphone-record and termux-tts-speak will not work."

# ---- Create virtual environment ---------------------------------------------
header "Creating voice-assistant virtual environment"

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
    info "Virtual environment already exists at $VENV_DIR."
else
    mkdir -p "$(dirname "$VENV_DIR")"
    echo -e "  Creating venv at ${YELLOW}${VENV_DIR}${NC} ..."
    python -m venv "$VENV_DIR"
    info "Virtual environment created at $VENV_DIR."
fi

# ---- Install Python packages in the venv ------------------------------------
header "Installing Python packages"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

PIP_PACKAGES=(anthropic requests)

for pkg in "${PIP_PACKAGES[@]}"; do
    if python -m pip show "$pkg" &>/dev/null; then
        info "$pkg is already installed in venv."
    else
        echo -e "  Installing ${YELLOW}${pkg}${NC} ..."
        if python -m pip install "$pkg"; then
            info "$pkg installed."
        else
            error "Failed to install $pkg."
        fi
    fi
done

deactivate

# ---- Create assistant directory ---------------------------------------------
header "Creating voice assistant"

mkdir -p "$ASSISTANT_DIR"

# ---- Write assistant.py ----------------------------------------------------
cat > "$ASSISTANT_DIR/assistant.py" << 'PYEOF'
#!/usr/bin/env python3
"""
Voice assistant for Quest 3 via Termux.

Uses energy-based VAD (amplitude threshold) for wake word detection,
termux-microphone-record for audio capture, and either the Anthropic API
(claude-sonnet-4-20250514) or a local Ollama instance for responses.
Speaks responses via termux-tts-speak.

Usage:
    python assistant.py                  # defaults to "hey ctrl"
    python assistant.py --wake "hey ai"  # custom wake phrase
    OLLAMA_HOST=http://192.168.1.35:11434 python assistant.py  # use Ollama
"""

import argparse
import json
import os
import signal
import struct
import subprocess
import sys
import tempfile
import time
import wave

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_WAKE_PHRASE = "hey ctrl"
RECORD_SECONDS = 5          # how long to record after wake detection
SAMPLE_RATE = 16000          # 16 kHz mono
AMPLITUDE_THRESHOLD = 3000   # energy threshold for VAD (tune for environment)
SILENCE_WINDOW = 0.5         # seconds of silence before stopping VAD listen
LISTEN_CHUNK_SECONDS = 1     # chunk size for VAD monitoring
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
OLLAMA_MODEL = "phi3:mini"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def speak(text):
    """Speak text via termux-tts-speak."""
    try:
        subprocess.run(
            ["termux-tts-speak", text],
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        print(f"[TTS] termux-tts-speak not found. Response: {text}")
    except subprocess.TimeoutExpired:
        print("[TTS] Speech timed out.")


def record_audio(filepath, duration=RECORD_SECONDS):
    """Record audio using termux-microphone-record and return the path."""
    # Start recording in background
    rec_proc = subprocess.Popen(
        [
            "termux-microphone-record",
            "-f", filepath,
            "-r", str(SAMPLE_RATE),
            "-c", "1",
            "-l", str(duration),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for recording to finish
    time.sleep(duration + 1)
    # Stop recording
    subprocess.run(
        ["termux-microphone-record", "-q"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rec_proc.wait(timeout=5)
    return filepath


def compute_rms(audio_path):
    """Compute RMS amplitude of a WAV file for energy-based VAD."""
    try:
        with wave.open(audio_path, "rb") as wf:
            n_frames = wf.getnframes()
            if n_frames == 0:
                return 0
            raw = wf.readframes(n_frames)
            # Assume 16-bit signed PCM
            n_samples = len(raw) // 2
            if n_samples == 0:
                return 0
            samples = struct.unpack(f"<{n_samples}h", raw)
            rms = (sum(s * s for s in samples) / n_samples) ** 0.5
            return rms
    except Exception:
        return 0


def listen_for_wake(threshold=AMPLITUDE_THRESHOLD):
    """
    Listen continuously using energy-based VAD.

    Records short chunks and checks if the RMS amplitude exceeds the
    threshold, indicating someone is speaking. Returns True when speech
    is detected. This is a simple energy gate — not keyword detection —
    as Porcupine is unavailable on Quest 3.
    """
    print("[VAD] Listening for speech (amplitude threshold) ...")
    while True:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            record_audio(tmp_path, duration=LISTEN_CHUNK_SECONDS)
            rms = compute_rms(tmp_path)
            if rms > threshold:
                print(f"[VAD] Speech detected (RMS={rms:.0f} > {threshold})")
                return True
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# LLM Backends
# ---------------------------------------------------------------------------

def query_anthropic(prompt):
    """Send prompt to Anthropic API and return the response text."""
    try:
        import anthropic
    except ImportError:
        print("[ERROR] anthropic package not installed. Run: pip install anthropic")
        return "I cannot respond right now. The Anthropic package is missing."

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "No Anthropic API key set. Export ANTHROPIC_API_KEY in your shell."

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            system="You are a concise voice assistant running on a Meta Quest 3 headset via Termux. Keep answers short and spoken-friendly — no markdown, no bullet points, no code blocks unless asked.",
        )
        return message.content[0].text
    except Exception as e:
        return f"Anthropic API error: {e}"


def query_ollama(prompt, host=None):
    """Send prompt to a local Ollama instance via HTTP API."""
    import requests

    host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    url = f"{host}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json().get("response", "No response from Ollama.")
    except requests.ConnectionError:
        return f"Cannot reach Ollama at {host}. Is the server running?"
    except Exception as e:
        return f"Ollama error: {e}"


def query_llm(prompt):
    """Route to Ollama if OLLAMA_HOST is set, otherwise use Anthropic."""
    if os.environ.get("OLLAMA_HOST"):
        print("[LLM] Using Ollama backend")
        return query_ollama(prompt)
    else:
        print("[LLM] Using Anthropic API backend")
        return query_anthropic(prompt)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Quest 3 Voice Assistant")
    parser.add_argument(
        "--wake", "-w",
        default=DEFAULT_WAKE_PHRASE,
        help=f"Wake phrase (default: '{DEFAULT_WAKE_PHRASE}')",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=AMPLITUDE_THRESHOLD,
        help=f"VAD amplitude threshold (default: {AMPLITUDE_THRESHOLD})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one interaction then exit (useful for testing)",
    )
    args = parser.parse_args()

    # Graceful shutdown
    def handle_signal(sig, frame):
        print("\n[EXIT] Shutting down voice assistant.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    backend = "Ollama" if os.environ.get("OLLAMA_HOST") else "Anthropic"
    print(f"[START] Voice assistant active — wake phrase: '{args.wake}'")
    print(f"[START] Backend: {backend}")
    print(f"[START] VAD threshold: {args.threshold}")
    print("[START] Press Ctrl+C to stop.\n")

    speak(f"Voice assistant ready. Say {args.wake} to begin.")

    while True:
        # Step 1: Wait for speech via energy-based VAD
        listen_for_wake(threshold=args.threshold)

        # Step 2: Notify user and record the actual query
        speak("I'm listening.")
        print("[REC] Recording query ...")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            query_path = tmp.name

        try:
            record_audio(query_path, duration=RECORD_SECONDS)

            # Step 3: Transcription placeholder
            # Termux does not have a local STT engine. For now, use a
            # simple prompt. In production, pipe audio to Whisper API or
            # a local whisper.cpp build.
            print("[NOTE] Local STT is not available on Quest 3 Termux.")
            print("[NOTE] Using text input fallback.")
            prompt = input("[INPUT] Type your query (or 'quit' to exit): ").strip()

            if prompt.lower() in ("quit", "exit", "q"):
                speak("Goodbye.")
                break

            if not prompt:
                speak("I didn't catch that. Try again.")
                continue

            # Step 4: Query LLM
            print(f"[QUERY] {prompt}")
            response = query_llm(prompt)
            print(f"[RESPONSE] {response}\n")

            # Step 5: Speak response
            speak(response)

        finally:
            try:
                os.unlink(query_path)
            except OSError:
                pass

        if args.once:
            break

    print("[EXIT] Voice assistant stopped.")


if __name__ == "__main__":
    main()
PYEOF

info "Created $ASSISTANT_DIR/assistant.py"

# ---- Write start.sh launcher -----------------------------------------------
cat > "$ASSISTANT_DIR/start.sh" << 'SHEOF'
#!/data/data/com.termux/files/usr/bin/bash
# ---------------------------------------------------------------------------
# start.sh - Launcher for Quest 3 voice assistant
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$HOME/venvs/voice-assistant"

echo "=== Quest 3 Voice Assistant ==="
echo ""

# Activate the virtual environment
if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    echo "[OK] Virtual environment activated."
else
    echo "[WARN] Venv not found at $VENV_DIR — using system Python."
fi

# Check for API key or Ollama
if [ -n "${OLLAMA_HOST:-}" ]; then
    echo "[OK] Using Ollama backend at $OLLAMA_HOST"
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "[OK] Using Anthropic API backend."
else
    echo "[ERROR] No backend configured."
    echo "  Set ANTHROPIC_API_KEY or OLLAMA_HOST in ~/.bashrc"
    exit 1
fi

echo ""
exec python "$SCRIPT_DIR/assistant.py" "$@"
SHEOF

chmod +x "$ASSISTANT_DIR/start.sh"
info "Created $ASSISTANT_DIR/start.sh"

# ---- Termux:Boot autostart (optional) ---------------------------------------
header "Configuring autostart (Termux:Boot)"

if [ -d "$BOOT_DIR" ] || command -v termux-boot &>/dev/null 2>&1; then
    mkdir -p "$BOOT_DIR"

    BOOT_SCRIPT="$BOOT_DIR/start-voice-assistant.sh"
    cat > "$BOOT_SCRIPT" << BOOTEOF
#!/data/data/com.termux/files/usr/bin/bash
# Autostart voice assistant on Termux boot
sleep 5  # wait for system to settle
exec $ASSISTANT_DIR/start.sh
BOOTEOF

    chmod +x "$BOOT_SCRIPT"
    info "Created boot script at $BOOT_SCRIPT."
    warn "Termux:Boot app must be installed from F-Droid for autostart to work."
else
    warn "Termux:Boot not detected. Skipping autostart configuration."
    warn "Install Termux:Boot from F-Droid to enable autostart, then re-run this script."
fi

# ---- Version summary --------------------------------------------------------
header "Version summary"

PY_VER=$(python --version 2>&1)
info "Python : $PY_VER"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
for pkg in "${PIP_PACKAGES[@]}"; do
    ver=$(python -m pip show "$pkg" 2>/dev/null | grep "^Version:" | cut -d' ' -f2)
    if [ -n "$ver" ]; then
        echo -e "    ${GREEN}${pkg}${NC} == ${ver}"
    else
        echo -e "    ${RED}${pkg}${NC}  (not found)"
    fi
done
deactivate

echo ""
info "Voice assistant setup complete."
echo ""
echo -e "  ${GREEN}Quick start:${NC}"
echo -e "    ~/voice-assistant/start.sh"
echo -e "    ~/voice-assistant/start.sh --wake 'hey ai'"
echo -e "    ~/voice-assistant/start.sh --threshold 2000"
echo ""
echo -e "  ${YELLOW}Ollama mode:${NC}"
echo -e "    export OLLAMA_HOST=http://192.168.1.35:11434"
echo -e "    ~/voice-assistant/start.sh"
echo ""
