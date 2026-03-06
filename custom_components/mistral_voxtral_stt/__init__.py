"""Mistral Voxtral STT integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_MODEL, CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from .const import _LOGGER, CONF_PROMPT, CONF_TEMPERATURE, DEFAULT_PROMPT, DEFAULT_TEMPERATURE
from .models import DEFAULT_MODEL

PLATFORMS = [Platform.STT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load entry."""
    _LOGGER.info("Setting up %s", entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update entry."""
    await hass.config_entries.async_reload(entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry to v2 schema."""
    _LOGGER.info(
        "Migration of %s from version %s.%s",
        config_entry.entry_id,
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 2:
        # Downgraded from a future version we don't understand.
        return False

    if config_entry.version < 2:
        # v1.x -> v2.0
        # Old schema stored CONF_SOURCE (provider index) and CONF_MODEL as
        # an integer index into the provider's model list, or as a string
        # for custom providers.  The v2 schema stores model name directly
        # and drops the provider concept entirely.
        old_data = {**config_entry.data}
        old_options = {**config_entry.options}

        new_data = {
            CONF_NAME: old_data.get(CONF_NAME, "Mistral Voxtral"),
            CONF_API_KEY: old_data.get(CONF_API_KEY, ""),
        }

        # Try to preserve the model name if the old entry was Mistral
        # (CONF_SOURCE == 2 in the old provider list).
        old_source = old_data.get("source")
        if old_source == 2:
            # Was Mistral — old model index 0 = voxtral-mini-latest
            new_model = "voxtral-mini-latest"
        else:
            # Was another provider; default to the realtime model.
            new_model = DEFAULT_MODEL

        # If the old model was stored as a string (custom provider), keep it
        # if it matches a known model name.
        old_model = old_options.get(CONF_MODEL)
        if isinstance(old_model, str) and old_model in (
            "voxtral-mini-latest",
            "voxtral-mini-transcribe-realtime-2602",
        ):
            new_model = old_model

        new_options = {
            CONF_MODEL: new_model,
            CONF_TEMPERATURE: old_options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
            CONF_PROMPT: old_options.get(CONF_PROMPT, DEFAULT_PROMPT),
        }

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options=new_options,
            version=2,
            minor_version=0,
        )

    _LOGGER.info("Migration of %s successful", config_entry.entry_id)
    return True
