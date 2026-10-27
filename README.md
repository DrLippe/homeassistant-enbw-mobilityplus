# EnBW mobility+ for Home Assistant

Dedicated Home Assistant integration for **EnBW mobility+** (`enbw_mobilityplus`). Other charging providers are intentionally outside the scope of this repository.

The integration includes the EnBW mobility+ app icon in `custom_components/enbw_mobilityplus/brand/icon.png` for Home Assistant 2026.3 and newer.

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

### Active charging monitor

The integration additionally polls `GET /v2/chargings/active` every 60 seconds, as identified in the EnBW Android application. It provides:

- **Ladevorgang aktiv** (binary sensor), true when the API reports at least one active session
- **Ladestatus** (`Inaktiv`, `Aktiv`, `Ende wird geprüft`, `Beendet`). `Beendet` requires two consecutive successful empty monitor responses following a previously active session; it remains until another session starts, but resets after a restart
- **Letzte gemeldete Ladeleistung** (kW), **Aktuell geladene Energie** (kWh), optional **Fahrzeug-Ladestand** (%), **Aktuelle Ladedauer** (min), **Aktuelle Ladekosten** (EUR) and **Ladeort** (address)
- **Letztes Ladeende** from the completed-session history (which can lag behind the live status)
- **Ladeart** (`AC`, `DC`, `Unbekannt`) from the active session's `chargePointType`, or the latest completed session's connector type if idle. Attributes `api_wert` and `datenquelle` show the original field and whether the result comes from the live monitor or history. Unrecognized connector types remain `Unbekannt` rather than being guessed from charging power.

On a confirmed completion the integration fires `enbw_mobilityplus_charge_completed` with `transaction_id` (if EnBW supplies it). Live measurements are unknown when no session is active, not zero. If the live endpoint fails, live entities become unavailable without disabling the established historical sensors.

**Important:** The EnBW response does **not** report whether a cable is physically plugged in. The active-session binary sensor is *not* a physical `eingesteckt` sensor. Similarly, `lastChargingPowerInKw` is the **last reported** charging power and need not represent instantaneous electrical flow. When multiple sessions are active, the individual live values display the first API entry.

## Implementation

`providers/enbw.py` wraps [`mawiak/enbw-mobilityplus-client`](https://github.com/mawiak/enbw-mobilityplus-client), installed through the pinned `manifest.json` dependency. `model.py` defines the charging-session and history snapshot models used by the sensors.

**Migration note:** If you installed an earlier development version under `charge_provider`, remove that integration and its custom component before installing this version. Home Assistant treats `enbw_mobilityplus` as a new integration domain, so entity identifiers may change.

The client is an unofficial reverse-engineered API implementation, distributed under the MIT license. This integration is not endorsed by EnBW. Use only your own account and respect the service's terms and limits. Credentials are saved in Home Assistant's config-entry storage; never share configuration backups containing credentials.
