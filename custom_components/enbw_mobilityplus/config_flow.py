"""EnBW mobility+ configuration flow."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN
from .providers.enbw import EnBWProvider


class EnBWMobilityPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Register EnBW mobility+ accounts."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()
            provider = EnBWProvider(email, user_input[CONF_PASSWORD])
            try:
                await self.hass.async_add_executor_job(provider.fetch)
            except Exception:  # API failures vary across backend versions
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"EnBW mobility+ ({email})",
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
            finally:
                await self.hass.async_add_executor_job(provider.close)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
