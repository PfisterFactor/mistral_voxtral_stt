# Mistral Voxtral STT integration for Home Assistant

This Home Assistant custom integration uses Mistral AI's Voxtral models for cloud-based speech-to-text, reducing workload on the Home Assistant server.

## Models

### Voxtral Mini (Offline)

- **`voxtral-mini-latest`** -- Batch transcription with high accuracy, speaker diarization, and multilingual support. Uses the REST API (`/v1/audio/transcriptions`).

### Voxtral Realtime

- **`voxtral-mini-transcribe-realtime-2602`** -- Live transcription with ultra-low latency via WebSocket streaming. Audio is forwarded to Mistral as it arrives from Home Assistant, so transcription begins while the user is still speaking. **This is the default model.**

Both models support 13 languages: Arabic, Chinese, Dutch, English, French, German, Hindi, Italian, Japanese, Korean, Portuguese, Russian, and Spanish.

## Requirements

- A Mistral AI account -- [Sign up](https://auth.mistral.ai/ui/registration)
- An API key -- [Generate one](https://console.mistral.ai/api-keys)

## How to install

### HACS

1. **Add** [this repository](https://my.home-assistant.io/redirect/hacs_repository/?owner=fabio-garavini&repository=ha-openai-whisper-stt-api&category=integration) to your HACS repositories:

    [![Add Repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=fabio-garavini&repository=ha-openai-whisper-stt-api&category=integration)

2. **Install** the `Mistral Voxtral STT` integration
3. **Restart** Home Assistant

### Manual Install

1. **Download** this repository
2. **Copy** everything inside the `custom_components` folder into your Home Assistant's `custom_components` folder.
3. **Restart** Home Assistant

## Configuration

- `api_key`: (Required) Mistral AI API key
- `model`: (Required) `voxtral-mini-transcribe-realtime-2602` (default, lowest latency) or `voxtral-mini-latest` (offline batch)
- `temperature`: (Optional) Sampling temperature between 0 and 1. Default `0`
- `prompt`: (Optional) Improve speech recognition of specific words or names. Provide a comma-separated list. Example: `"open, close, Chat GPT-3"`

Configure via your Home Assistant Dashboard (YAML configuration not supported).

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mistral_voxtral_stt)

Or navigate to **Devices & services** and click **+ Add Integration**.
