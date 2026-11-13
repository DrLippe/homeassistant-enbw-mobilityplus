"""EnBW mobility+ configuration flow.

Save credentials without requiring the EnBW/Auth0 service to be reachable.
The integration validates credentials during setup and retries if unavailable.
"""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN
from .tariff import DEFAULTS


class EnBWMobilityPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Register EnBW mobility+ accounts."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EnBWOptionsFlow()

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


class EnBWOptionsFlow(config_entries.OptionsFlow):
    """Manually configured S/M/L prices and tariff switch dates."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = {
            vol.Required(
                "current_tariff", default=options.get("current_tariff", DEFAULTS["current_tariff"])
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["S", "M", "L"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
        for key, default in DEFAULTS.items():
            if key.startswith("tariff_") and key != "tariff_prices_checked":
                schema[vol.Required(key, default=options.get(key, default))] = vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=200)
                )
        schema[
            vol.Required(
                "tariff_prices_checked",
                default=options.get(
                    "tariff_prices_checked", DEFAULTS["tariff_prices_checked"]
                ),
            )
        ] = selector.DateSelector()
        for key in ("tariff_started_on", "tariff_next_switch_on"):
            schema[
                vol.Optional(
                    key,
                    description={"suggested_value": options[key]} if options.get(key) else {},
                )
            ] = selector.DateSelector()
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
