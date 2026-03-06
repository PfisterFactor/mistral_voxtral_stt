"""Mistral Voxtral speech-to-text entity."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import wave
from collections.abc import AsyncIterable
from urllib.parse import urlencode, urlunparse

import aiohttp
import requests

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import _LOGGER
from .const import CONF_PROMPT, CONF_TEMPERATURE, MISTRAL_API_URL
from .whisper_provider import MODELS_BY_NAME, ModelType, VoxtralModel


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Voxtral speech platform via config entry."""
    _LOGGER.debug("STT setup Entry %s", config_entry.entry_id)

    model_name = config_entry.options[CONF_MODEL]
    model = MODELS_BY_NAME.get(model_name)
    if model is None:
        _LOGGER.error("Unknown model %s", model_name)
        return

    async_add_entities(
        [
            MistralVoxtralSTTEntity(
                api_key=config_entry.data.get(CONF_API_KEY, ""),
                model=model,
                temperature=config_entry.options[CONF_TEMPERATURE],
                prompt=config_entry.options[CONF_PROMPT],
                name=config_entry.data[CONF_NAME],
                unique_id=config_entry.entry_id,
            )
        ]
    )


class MistralVoxtralSTTEntity(SpeechToTextEntity):
    """Mistral Voxtral STT entity."""

    def __init__(
        self,
        api_key: str,
        model: VoxtralModel,
        temperature: float,
        prompt: str,
        name: str,
        unique_id: str,
    ) -> None:
        """Init STT service."""
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.prompt = prompt
        self._attr_name = name
        self._attr_unique_id = unique_id

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self.model.languages

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bit rates."""
        return [
            AudioBitRates.BITRATE_8,
            AudioBitRates.BITRATE_16,
            AudioBitRates.BITRATE_24,
            AudioBitRates.BITRATE_32,
        ]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [
            AudioSampleRates.SAMPLERATE_8000,
            AudioSampleRates.SAMPLERATE_16000,
            AudioSampleRates.SAMPLERATE_44100,
            AudioSampleRates.SAMPLERATE_48000,
        ]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO, AudioChannels.CHANNEL_STEREO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service."""
        _LOGGER.debug("Processing audio stream: %s", metadata)

        if self.model.model_type == ModelType.REALTIME:
            return await self._transcribe_realtime(metadata, stream)
        return await self._transcribe_rest(metadata, stream)

    # ------------------------------------------------------------------
    # REST transport — offline batch model (voxtral-mini-latest)
    # ------------------------------------------------------------------

    async def _transcribe_rest(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Buffer audio, wrap in WAV, POST to /v1/audio/transcriptions."""
        data = b""
        async for chunk in stream:
            data += chunk
            if len(data) / (1024 * 1024) > 24.5:
                _LOGGER.error(
                    "Audio stream exceeds the 25 MB maximum"
                )
                return SpeechResult("", SpeechResultState.ERROR)

        if not data:
            _LOGGER.error("No audio data received")
            return SpeechResult("", SpeechResultState.ERROR)

        try:
            temp_file = io.BytesIO()
            with wave.open(temp_file, "wb") as wav_file:
                wav_file.setnchannels(metadata.channel)
                wav_file.setframerate(metadata.sample_rate)
                wav_file.setsampwidth(2)
                wav_file.writeframes(data)
            temp_file.seek(0)

            _LOGGER.debug(
                "WAV audio file created: %.2f MB",
                temp_file.getbuffer().nbytes / (1024 * 1024),
            )

            files = {"file": ("audio.wav", temp_file, "audio/wav")}
            form_data = {
                "model": self.model.name,
                "language": metadata.language,
                "temperature": self.temperature,
                "response_format": "json",
            }
            if self.prompt:
                # Mistral uses context_bias (list of words) instead of
                # OpenAI's prompt parameter.
                words = [w.strip() for w in self.prompt.split(",") if w.strip()]
                if words:
                    form_data["context_bias"] = json.dumps(words)

            response = await asyncio.to_thread(
                requests.post,
                f"{MISTRAL_API_URL}/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data=form_data,
            )

            _LOGGER.debug(
                "Transcription request took %f s — %d %s",
                response.elapsed.total_seconds(),
                response.status_code,
                response.reason,
            )

            transcription = response.json().get("text", "")
            _LOGGER.debug("TRANSCRIPTION: %s", transcription)

            if not transcription:
                _LOGGER.error(response.text)
                return SpeechResult("", SpeechResultState.ERROR)

            return SpeechResult(transcription, SpeechResultState.SUCCESS)

        except requests.exceptions.RequestException as exc:
            _LOGGER.error(exc)
            return SpeechResult("", SpeechResultState.ERROR)

    # ------------------------------------------------------------------
    # WebSocket transport — realtime model
    # ------------------------------------------------------------------

    async def _transcribe_realtime(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Stream audio over WebSocket, collect transcription deltas."""
        ws_url = self._build_ws_url()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        transcription_parts: list[str] = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    ws_url,
                    headers=headers,
                    timeout=aiohttp.ClientWSTimeout(ws_close=10.0),
                ) as ws:
                    # --- handshake: wait for session.created ---------------
                    if not await self._ws_wait_for_session(ws):
                        return SpeechResult("", SpeechResultState.ERROR)

                    # --- configure audio format ----------------------------
                    await ws.send_json(
                        {
                            "type": "session.update",
                            "session": {
                                "audio_format": {
                                    "encoding": self._pcm_encoding(metadata),
                                    "sample_rate": metadata.sample_rate,
                                },
                            },
                        }
                    )

                    # --- concurrent send / receive -------------------------
                    async def _send_audio() -> None:
                        async for chunk in stream:
                            if ws.closed:
                                break
                            payload = {
                                "type": "input_audio.append",
                                "audio": base64.b64encode(chunk).decode(
                                    "ascii"
                                ),
                            }
                            await ws.send_json(payload)
                        # signal end-of-audio
                        if not ws.closed:
                            await ws.send_json(
                                {"type": "input_audio.flush"}
                            )
                            await ws.send_json(
                                {"type": "input_audio.end"}
                            )

                    send_task = asyncio.create_task(_send_audio())

                    try:
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                event = json.loads(msg.data)
                                ev_type = event.get("type")

                                if ev_type == "transcription.text.delta":
                                    text = event.get("text", "")
                                    if text:
                                        transcription_parts.append(text)

                                elif ev_type == "transcription.done":
                                    _LOGGER.debug("Realtime transcription done")
                                    break

                                elif ev_type == "error":
                                    err = event.get("error", {})
                                    _LOGGER.error(
                                        "Realtime transcription error: %s",
                                        err.get("message", err),
                                    )
                                    return SpeechResult(
                                        "", SpeechResultState.ERROR
                                    )

                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                _LOGGER.error(
                                    "WebSocket closed unexpectedly: %s",
                                    msg.data,
                                )
                                return SpeechResult(
                                    "", SpeechResultState.ERROR
                                )
                    finally:
                        send_task.cancel()
                        try:
                            await send_task
                        except asyncio.CancelledError:
                            pass

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            _LOGGER.error("Realtime transcription failed: %s", exc)
            return SpeechResult("", SpeechResultState.ERROR)

        text = "".join(transcription_parts).strip()
        _LOGGER.debug("TRANSCRIPTION: %s", text)

        if not text:
            _LOGGER.error("Realtime transcription returned empty text")
            return SpeechResult("", SpeechResultState.ERROR)

        return SpeechResult(text, SpeechResultState.SUCCESS)

    def _build_ws_url(self) -> str:
        """Build the WSS URL for the realtime transcription endpoint."""
        params = urlencode({"model": self.model.name})
        return urlunparse(
            ("wss", "api.mistral.ai", "/v1/audio/transcriptions/realtime", "", params, "")
        )

    @staticmethod
    async def _ws_wait_for_session(ws: aiohttp.ClientWebSocketResponse) -> bool:
        """Wait for the session.created handshake event."""
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=10.0)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout waiting for realtime session creation")
            return False

        if msg.type != aiohttp.WSMsgType.TEXT:
            _LOGGER.error("Unexpected WS message during handshake: %s", msg.type)
            return False

        event = json.loads(msg.data)
        if event.get("type") != "session.created":
            _LOGGER.error("Expected session.created, got %s", event.get("type"))
            return False

        _LOGGER.debug("Realtime session created")
        return True

    @staticmethod
    def _pcm_encoding(metadata: SpeechMetadata) -> str:
        """Map HA bit rate to Mistral PCM encoding string."""
        return "pcm_s16le"
