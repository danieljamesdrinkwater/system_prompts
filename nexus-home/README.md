# Nexus Home

Self-hosted smart home AI server combining device automation, local AI, voice control, personal cloud storage, calendar/mail integration, VoIP telephony, and CCTV with vision AI.

## Features

- **Smart Device Control** — MQTT-based Tasmota/ESPHome device management
- **AI Assistant** — Local Ollama inference for chat, intent parsing, email summarization
- **Voice Control** — Speech-to-text (faster-whisper) + text-to-speech (Piper)
- **Personal Cloud Storage** — Auto-detect and mount drives, file browser with upload/download
- **Calendar** — CalDAV + Google Calendar sync with event-triggered automations
- **Mail** — IMAP inbox + SMTP send with AI-assisted management
- **VoIP Telephony** — SIP-based calls with AI auto-attendant and voicemail
- **CCTV** — RTSP/USB/ONVIF cameras with YOLOv8 person/object detection
- **Automation** — Rules, scenes, and cron-like scheduled tasks
- **Energy Monitoring** — Track power consumption from smart plugs
- **Notifications** — Email, webhooks, and ntfy.sh push notifications

## Quick Start

```bash
# Clone and setup
cd nexus-home
./scripts/setup.sh
```

This will:
1. Create `config.yaml` from the template
2. Generate a random API key
3. Start Docker services (app, Mosquitto MQTT, Ollama)
4. Pull the default AI model (llama3.2)

## Manual Setup

```bash
# Copy and edit config
cp config.example.yaml config.yaml
# Edit config.yaml with your settings

# Start services
docker compose up -d

# Pull AI model
docker compose exec ollama ollama pull llama3.2
```

## Access

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| MQTT Broker | localhost:1883 |
| Ollama | http://localhost:11434 |

## Configuration

Edit `config.yaml` to configure:

- **MQTT** — Broker connection for Tasmota/ESPHome devices
- **AI** — Ollama URL and model selection
- **Voice** — STT model size, TTS voice model
- **Storage** — Base path, upload limits, auto-mount
- **Calendar** — CalDAV server and/or Google Calendar credentials
- **Mail** — IMAP/SMTP server settings
- **Telephony** — SIP provider credentials
- **Cameras** — Detection model, confidence threshold, recording retention
- **Notifications** — SMTP, webhooks, ntfy.sh topic

## API

All endpoints require an API key via the `X-API-Key` header.

### Devices
- `GET /api/devices/` — List devices
- `POST /api/devices/` — Register device
- `POST /api/devices/{id}/command` — Send command
- `GET /api/devices/discover/` — Network discovery

### Cameras
- `GET /api/cameras/` — List cameras
- `POST /api/cameras/` — Add camera
- `GET /api/cameras/{id}/snapshot` — Current frame
- `GET /api/cameras/{id}/stream` — MJPEG live stream
- `GET /api/cameras/{id}/events` — Detection events
- `POST /api/cameras/discover` — ONVIF auto-discovery

### AI & Voice
- `POST /api/ai/chat` — Chat with AI assistant
- `POST /api/ai/command` — Natural language device control
- `POST /api/voice/transcribe` — Speech-to-text
- `POST /api/voice/speak` — Text-to-speech
- `POST /api/voice/command` — Full voice command pipeline

### Calendar & Mail
- `GET /api/calendar/events` — Upcoming events
- `POST /api/calendar/sync` — Sync from CalDAV/Google
- `GET /api/mail/inbox` — List messages
- `POST /api/mail/send` — Send email

### Telephony
- `POST /api/telephony/dial` — Make a call
- `GET /api/telephony/history` — Call history

### Storage
- `GET /api/storage/files` — Browse files
- `POST /api/storage/files/upload` — Upload file
- `GET /api/storage/disks` — List drives
- `POST /api/storage/auto-mount` — Auto-mount drives

### Automation
- `GET /api/automation/rules` — List rules
- `POST /api/automation/scenes/{id}/activate` — Activate scene
- `GET /api/automation/schedules` — List schedules

## Device Setup

### Tasmota
Configure your Tasmota devices to use the MQTT broker:
- Host: `<server-ip>`
- Port: `1883`
- Topic: `<device-name>`

### ESPHome
Add MQTT to your ESPHome config:
```yaml
mqtt:
  broker: <server-ip>
  port: 1883
```

## Architecture

```
Docker Compose
├── app (FastAPI + Python 3.12)
├── mosquitto (MQTT Broker)
└── ollama (Local AI)
```

## License

MIT
