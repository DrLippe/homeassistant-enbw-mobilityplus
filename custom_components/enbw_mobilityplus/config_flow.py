"""EnBW mobility+ configuration flow.

Save credentials without requiring the EnBW/Auth0 service to be reachable.
The integration validates credentials during setup and retries if unavailable.
"""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN


class EnBWMobilityPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Register EnBW mobility+ accounts."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"EnBW mobility+ ({email})",
                data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
        )
