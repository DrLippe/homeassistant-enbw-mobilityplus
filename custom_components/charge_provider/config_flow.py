"""UI-based configuration of charging providers."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import CONF_PROVIDER, DOMAIN, PROVIDER_ENBW
from .providers.enbw import EnBWProvider


class ChargeProviderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Register multiple providers and accounts."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return await self.async_step_enbw()
        return self.async_show_menu(step_id="user", menu_options=["enbw"])

    async def async_step_enbw(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            await self.async_set_unique_id(f"{PROVIDER_ENBW}:{email}")
            self._abort_if_unique_id_configured()
            provider = EnBWProvider(email, user_input[CONF_PASSWORD])
            try:
                await self.hass.async_add_executor_job(provider.fetch)
            except Exception:  # API failures vary across backend versions
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"EnBW mobility+ ({email})",
                    data={CONF_PROVIDER: PROVIDER_ENBW, CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
            finally:
                await self.hass.async_add_executor_job(provider.close)
        return self.async_show_form(
            step_id="enbw",
            data_schema=vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
