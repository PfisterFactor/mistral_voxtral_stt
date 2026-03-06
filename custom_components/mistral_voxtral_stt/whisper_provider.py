"""Mistral Voxtral model definitions."""

from enum import Enum

from .const import SUPPORTED_LANGUAGES


class ModelType(Enum):
    """Transport used by the model."""

    REST = "rest"
    REALTIME = "realtime"


class VoxtralModel:
    """A Voxtral transcription model."""

    def __init__(
        self,
        name: str,
        model_type: ModelType,
        languages: list[str] | None = None,
    ) -> None:
        """Init."""
        self.name = name
        self.model_type = model_type
        self.languages = languages or SUPPORTED_LANGUAGES


MODELS: list[VoxtralModel] = [
    VoxtralModel(
        "voxtral-mini-latest",
        ModelType.REST,
    ),
    VoxtralModel(
        "voxtral-mini-transcribe-realtime-2602",
        ModelType.REALTIME,
    ),
]

DEFAULT_MODEL = "voxtral-mini-transcribe-realtime-2602"

MODELS_BY_NAME: dict[str, VoxtralModel] = {m.name: m for m in MODELS}
