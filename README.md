# Charge Provider – EnBW mobility+

Custom integration for Home Assistant. The repository starts with EnBW mobility+ but uses the generic **`charge_provider`** domain so that additional services can use the same entity contract.

## Install

1. In HACS → Custom repositories, add `https://github.com/DrLippe/homeassistant-enbw-mobilityplus` as an **Integration**.
2. Install and restart Home Assistant.
3. Settings → Devices & services → Add integration → **Charge Provider** → **EnBW mobility+**.
4. Enter the account's email and password. Multiple accounts are supported.

## Entities (per account)

| Entity | Value |
| --- | --- |
| Total energy | Sum of fetched historical charging energy, kWh |
| Total cost | Sum of fetched historical total costs, EUR |
| Total sessions | Count of fetched sessions |
| Last charge | Start timestamp of newest completed charge, with additional details |
| Last energy | Energy of newest completed session, kWh |
| Last cost | Total cost of newest completed session, EUR |
| Last station | Address of newest completed session |
| Last duration | Duration of newest completed session, minutes |

Data is refreshed every 30 minutes. History pagination is capped at 10,000 records as a safety limit. Totals reflect the history returned by EnBW, not necessarily all lifetime consumption if EnBW truncates its history. A sensor will be unavailable if its initial fetch fails.

The upstream client currently **does not** offer tariff details, active charging session state, plugged-in status, or real-time charger power. These are not inferred from old sessions.

## Architecture

`providers/enbw.py` wraps [`mawiak/enbw-mobilityplus-client`](https://github.com/mawiak/enbw-mobilityplus-client), installed through the pinned `manifest.json` dependency. `model.py` defines `ChargeSession` and `ProviderSnapshot`. The coordinator and sensor platform operate exclusively on these normalized models; future adapters for other providers can implement the same contract.

The client is an unofficial reverse-engineered API implementation, distributed under the MIT license. This integration is not endorsed by EnBW. Use only your own account and respect the service's terms and limits. Credentials are saved in Home Assistant's config-entry storage; never share configuration backups containing credentials.
