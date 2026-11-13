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

Data is refreshed every 60 minutes. History pagination is capped at 10,000 records as a safety limit. Totals reflect the history returned by EnBW, not necessarily all lifetime consumption if EnBW truncates its history. A sensor will be unavailable if its initial fetch fails.

### Active charging monitor

The integration additionally polls `GET /v2/chargings/active` every 30 seconds during active charging and every 5 minutes when idle, as identified in the EnBW Android application. It provides:

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

## Authentication and troubleshooting

Access tokens are refreshed using the upstream client's refresh-token grant shortly before expiry (two-minute margin). If EnBW rejects a request with HTTP 401, the integration first refreshes and retries; if authorization still fails or the refresh token is invalid, it performs a new email/password login. HTTP 403 and unrelated network/server errors are **not** treated as expired tokens. Sessions and tokens live in memory; credentials remain in Home Assistant's config entry.

Setup, configuration-flow, historical and live-request errors are logged under `custom_components.enbw_mobilityplus` with the failing stage and, where available, HTTP status. Server response bodies, passwords and tokens are deliberately omitted. In Home Assistant, inspect **Settings → System → Logs**, or add the following temporarily for more detailed log context:

```yaml
logger:
  logs:
    custom_components.enbw_mobilityplus: debug
```

## Release v0.2.4 – stable mawiak authentication

EnBW mobility+ uses the upstream `enbw-mobilityplus-client==1.0.1` directly.
The additional Auth0 HTTPX response hook has been removed after confirming
that login succeeds without it in Home Assistant. The upstream client's OAuth
logic and all existing charging-history and live-session features are unchanged.
A one-time, opt-in runtime comparison is available at DEBUG level under
`custom_components.enbw_mobilityplus.providers.enbw`; no credentials, session
cookies or tokens are logged. The integration introduced this reliable login behavior in v0.2.4.

## Polling schedule (v0.2.5)

The update schedule matches the EWE Go integration: active-session requests every
**30 seconds while charging**, and every **5 minutes when idle**. Charging
history refreshes every **60 minutes**, plus on initial setup and when charging
completion has been confirmed by two consecutive empty live responses. The
history coordinator remains independent of the live coordinator, and failed
live API requests do not get mistaken for an ended session.


## Tariff card (v0.3.0)

The optional **EnBW tariff comparison** is adapted from
[sluggyly1991/enbw-mobilityplus-homeassistant](https://github.com/sluggyly1991/enbw-mobilityplus-homeassistant)
under the MIT license. Copyright and licensing terms are retained in
`custom_components/enbw_mobilityplus/LICENSE.upstream`. The dashboard card is
bundled in the integration; there is no additional HACS installation for it.

1. Update the integration to 0.3.0 and restart Home Assistant.
2. Open **Settings → Devices & services → EnBW mobility+ → Configure** and select
   your current S, M, or L tariff. Check the monthly base fees and ct/kWh for all
   three tiers and **confirm the tariff prices' verification date**. Optional
   switch dates may be entered here as well. The prices are example defaults,
   not official live EnBW tariff data, and may be obsolete.
3. Add a **Dashboard resource** (JavaScript module) at:
   `/enbw-mobilityplus/enbw-tariff-card.js?v=0.3.0`.
4. Add a manual dashboard card (replace both example entity IDs with the actual
   entities listed on your EnBW device):

```yaml
type: custom:enbw-tariff-card
entity: sensor.replace_with_tarifwechsel
refresh_entity: button.replace_with_historie_aktualisieren
language: de
```

The integration provides a **Tarifwechsel** sensor plus numeric **Tarifwechsel
Ersparnis**, **Tarifwechsel Wechselgrenze**, **Tarifwechsel Monatsverbrauch**, and
**Historie aktualisieren** button. The custom card reads the recommendation's
attributes, supports manually recording a current S/M/L plan and shows costs,
monthly savings and the calculated break-even threshold. Recording a tariff
change updates only Home Assistant settings; it **does not change the real
EnBW contract**. On multi-account installations, the card's recommendation
attributes identify the relevant config entry automatically.

The conservative tariff recommendation uses the three most recently completed
**local** calendar months, requires a historical entry before that window and
includes only EnBW-operated German EVSEs (prefix `DE*EBW*`). If the API history
cannot prove complete coverage, price data is over 31 days old, or tariffs
are invalid, the state is **Prüfen** (no advice). This historical cost projection
is not a promise of future savings. Tariff and dashboard calculations do not
request additional EnBW data. History polling remains hourly, with an additional
refresh when a charging session ends or when the button is pressed.

### Native dashboard examples

The `examples` directory includes `monthly-overview.yaml`,
`recent-charges.yaml`, and `charging-overview.yaml`. The integration
provides four local-month sensors (energy, cost, count and effective EUR/kWh)
and a `Ladehistorie` sensor whose `sessions` attribute contains at most
50 recently completed sessions. Missing session prices stay unknown rather
than being estimated. These native cards work independently of the JavaScript
tariff card and do not make extra EnBW API calls.
