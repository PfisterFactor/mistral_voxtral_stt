"""Config flow for Mistral Voxtral STT integration."""

from __future__ import annotations

import asyncio
from typing import Any

import requests
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_API_KEY, CONF_MODEL, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    _LOGGER,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    MISTRAL_API_URL,
)
from .whisper_provider import DEFAULT_MODEL, MODELS


# ---- Validation ---------------------------------------------------------


async def validate_api_key(api_key: str) -> None:
    """Validate the API key by listing models."""
    _LOGGER.debug("Validating API key")

    response = await asyncio.to_thread(
        requests.get,
        url=f"{MISTRAL_API_URL}/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    _LOGGER.debug(
        "Validation request returned %d %s",
        response.status_code,
        response.reason,
    )

    if response.status_code == 401:
        raise InvalidAPIKey
    if response.status_code == 403:
        raise UnauthorizedError
    if response.status_code != 200:
        raise UnknownError


# ---- Schemas -------------------------------------------------------------

MODEL_NAMES = [m.name for m in MODELS]


def _model_schema(default: str = DEFAULT_MODEL) -> vol.Schema:
    """Schema for the main setup / reconfigure form."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default="Mistral Voxtral"): cv.string,
            vol.Required(CONF_API_KEY): cv.string,
            vol.Required(CONF_MODEL, default=default): vol.In(MODEL_NAMES),
            vol.Optional(
                CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(CONF_PROMPT): cv.string,
        }
    )


# ---- Options flow --------------------------------------------------------


class OptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle Mistral Voxtral options."""

    config_entry: ConfigEntry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title,
                data={
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_TEMPERATURE: user_input.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                    CONF_PROMPT: user_input.get(CONF_PROMPT, DEFAULT_PROMPT),
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_MODEL): vol.In(MODEL_NAMES),
                        vol.Optional(CONF_TEMPERATURE): vol.All(
                            vol.Coerce(float), vol.Range(min=0, max=1)
                        ),
                        vol.Optional(CONF_PROMPT): cv.string,
                    }
                ),
                suggested_values={
                    CONF_MODEL: self.config_entry.options[CONF_MODEL],
                    CONF_TEMPERATURE: self.config_entry.options[CONF_TEMPERATURE],
                    CONF_PROMPT: self.config_entry.options.get(
                        CONF_PROMPT, DEFAULT_PROMPT
                    ),
                },
            ),
        )


# ---- Config flow ---------------------------------------------------------


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle UI config flow."""

    VERSION = 2
    MINOR_VERSION = 0

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Options callback."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Single-step setup: API key + model selection."""
        errors = errors or {}

        if user_input is not None:
            try:
                await validate_api_key(user_input[CONF_API_KEY])

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "Mistral Voxtral"),
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                    options={
                        CONF_MODEL: user_input[CONF_MODEL],
                        CONF_TEMPERATURE: user_input.get(
                            CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                        ),
                        CONF_PROMPT: user_input.get(CONF_PROMPT, DEFAULT_PROMPT),
                    },
                )

            except requests.exceptions.RequestException as exc:
                _LOGGER.error(exc)
                errors["base"] = "connection_error"
            except UnauthorizedError:
                errors["base"] = "unauthorized"
            except InvalidAPIKey:
                errors[CONF_API_KEY] = "invalid_api_key"
            except UnknownError:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=_model_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Reconfigure an existing entry."""
        errors = errors or {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            try:
                api_key = user_input.get(
                    CONF_API_KEY, entry.data.get(CONF_API_KEY, "")
                )
                await validate_api_key(api_key)

                self.hass.config_entries.async_update_entry(
                    entry=entry,
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_API_KEY: api_key,
                    },
                    options={
                        CONF_MODEL: user_input[CONF_MODEL],
                        CONF_TEMPERATURE: user_input.get(
                            CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                        ),
                        CONF_PROMPT: user_input.get(CONF_PROMPT, DEFAULT_PROMPT),
                    },
                )
                await self.hass.config_entries.async_reload(
                    self.context["entry_id"]
                )
                return self.async_abort(reason="reconfigure_successful")

            except requests.exceptions.RequestException as exc:
                _LOGGER.error(exc)
                errors["base"] = "connection_error"
            except UnauthorizedError:
                errors["base"] = "unauthorized"
            except InvalidAPIKey:
                errors[CONF_API_KEY] = "invalid_api_key"
            except UnknownError:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Optional(CONF_API_KEY): cv.string,
                        vol.Required(CONF_MODEL): vol.In(MODEL_NAMES),
                        vol.Optional(CONF_TEMPERATURE): vol.All(
                            vol.Coerce(float), vol.Range(min=0, max=1)
                        ),
                        vol.Optional(CONF_PROMPT): cv.string,
                    }
                ),
                suggested_values={
                    CONF_NAME: entry.data.get(CONF_NAME),
                    CONF_MODEL: entry.options.get(CONF_MODEL, DEFAULT_MODEL),
                    CONF_TEMPERATURE: entry.options.get(CONF_TEMPERATURE),
                    CONF_PROMPT: entry.options.get(CONF_PROMPT),
                },
            ),
            errors=errors,
        )


# ---- Exceptions ----------------------------------------------------------


class UnknownError(exceptions.HomeAssistantError):
    """Unknown error."""


class UnauthorizedError(exceptions.HomeAssistantError):
    """API key valid but doesn't have the rights to use the model."""


class InvalidAPIKey(exceptions.HomeAssistantError):
    """Invalid api_key error."""

