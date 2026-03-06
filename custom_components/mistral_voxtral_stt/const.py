"""Constants for the Mistral Voxtral STT integration."""

import logging

DOMAIN = "mistral_voxtral_stt"

_LOGGER = logging.getLogger(__name__)

CONF_PROMPT = "prompt"
CONF_TEMPERATURE = "temperature"

MISTRAL_API_URL = "https://api.mistral.ai"

# 13 languages supported by Voxtral models.
# https://docs.mistral.ai/capabilities/audio_transcription/
SUPPORTED_LANGUAGES = [
    "ar",
    "de",
    "en",
    "es",
    "fr",
    "hi",
    "it",
    "ja",
    "ko",
    "nl",
    "pt",
    "ru",
    "zh",
]

DEFAULT_PROMPT = ""
DEFAULT_TEMPERATURE = 0
