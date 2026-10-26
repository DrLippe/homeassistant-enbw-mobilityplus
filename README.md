# EnBW mobility+ for Home Assistant

Dedicated Home Assistant integration for **EnBW mobility+** (`enbw_mobilityplus`). Other charging providers are intentionally outside the scope of this repository.

## Install

1. In HACS → Custom repositories, add `https://github.com/DrLippe/homeassistant-enbw-mobilityplus` as an **Integration**.
2. Install and restart Home Assistant.
3. Settings → Devices & services → Add integration → **EnBW mobility+**.
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

## Implementation

`providers/enbw.py` wraps [`mawiak/enbw-mobilityplus-client`](https://github.com/mawiak/enbw-mobilityplus-client), installed through the pinned `manifest.json` dependency. `model.py` defines the charging-session and history snapshot models used by the sensors.

**Migration note:** If you installed an earlier development version under `charge_provider`, remove that integration and its custom component before installing this version. Home Assistant treats `enbw_mobilityplus` as a new integration domain, so entity identifiers may change.

The client is an unofficial reverse-engineered API implementation, distributed under the MIT license. This integration is not endorsed by EnBW. Use only your own account and respect the service's terms and limits. Credentials are saved in Home Assistant's config-entry storage; never share configuration backups containing credentials.
