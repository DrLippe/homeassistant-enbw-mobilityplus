/** EnBW mobility+ tariff card. MIT. No external dependencies or network requests. */
export function tariffView(state) {
  const a = state?.attributes || {};
  const numeric = ['monthly_savings', 'current_monthly_cost', 'target_monthly_cost', 'average_energy'];
  const valid = ['Ja', 'Nein'].includes(state?.state) && !a.restored &&
    numeric.every(k => typeof a[k] === 'number' && Number.isFinite(a[k])) &&
    ['S', 'M', 'L'].includes(a.current_tariff) && ['S', 'M', 'L'].includes(a.target_tariff) &&
    a.current_monthly_cost >= 0 && a.target_monthly_cost >= 0 && a.average_energy >= 0 &&
    (state.state === 'Ja' ? a.monthly_savings > 0 : a.monthly_savings <= 0);
  const locked=valid && state.state==='Ja' && a.switch_allowed===false && /^\d{4}-\d{2}-\d{2}$/.test(a.next_switch_on || '');
  return { ...a, valid, locked, change: valid && state.state === 'Ja', tone: valid ? (locked ? 'wait' : state.state === 'Ja' ? 'yes' : 'no') : 'check' };
}

const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const css = `
:host {display:block; container-type:inline-size; color:var(--primary-text-color,#202124); --muted:var(--secondary-text-color,#62666c); --line:var(--divider-color,#ddd); font-family:var(--ha-font-family-body,inherit);}
* {box-sizing:border-box;} ha-card {overflow:hidden; border-radius:var(--ha-card-border-radius,16px); background:var(--ha-card-background,var(--card-background-color,#fff));}
.card {--accent:#12653e; --tint:#e6f4eb; --ink:#12492f; --strong:#0c5030;} .card.no {--accent:#1857a4;--tint:#e8f0fc;--ink:#193e73;--strong:#174c90;} .card.check,.card.wait {--accent:#885000;--tint:#fff0d5;--ink:#664000;--strong:#744500;}
.card.dark {--accent:#8de2b4;--tint:#173b2a;--ink:#c4f2d7;--strong:#a1ebc0;} .card.dark.no {--accent:#a6c8ff;--tint:#1e3454;--ink:#d1e2ff;--strong:#b4d1ff;} .card.dark.check,.card.dark.wait {--accent:#ffcf88;--tint:#4a3418;--ink:#ffdfad;--strong:#ffcf88;}
header {display:flex;align-items:center;gap:9px;padding:16px 24px 12px;font-weight:600;font-size:16px;} header ha-icon {color:var(--muted);--mdc-icon-size:21px;}
.decision {display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:20px;background:var(--tint); color:var(--ink); padding:17px 24px 19px;}
.verdict {grid-column:1;grid-row:1;display:flex;align-items:center;gap:11px;margin:0 0 9px;font-size:27px;font-weight:700;line-height:1.2;letter-spacing:-.02em;overflow-wrap:anywhere;} .verdict ha-icon {--mdc-icon-size:29px;flex-shrink:0;color:var(--accent);}
.route {grid-column:1;grid-row:2;font-size:14px;line-height:1.5;margin:0 0 9px;} .saving {grid-column:2;grid-row:1;text-align:right;font-size:31px;font-weight:700;letter-spacing:-.025em;line-height:1.15;font-variant-numeric:tabular-nums;color:var(--strong);} .saving-label {grid-column:2;grid-row:2;text-align:right;max-width:170px;font-size:14px;line-height:1.5;margin:4px 0 0;}
.body {padding:6px 24px 0;} .costs {width:100%;border-collapse:collapse;font-size:14px;} .costs th,.costs td {padding:12px 0;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;} .costs td:last-child,.costs th:last-child {text-align:right;padding-left:12px;} .costs th {font-weight:400;color:var(--muted);padding-top:16px;padding-bottom:9px;font-size:12px;} .costs strong {font-size:19px;font-weight:650;font-variant-numeric:tabular-nums;white-space:nowrap;} .costs .best strong {color:var(--accent);} .tariff {font-weight:600;} .sub {display:block;color:var(--muted);font-size:12px;line-height:1.5;margin-top:3px;}
.facts {display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:14px 0 0;} .facts dt {font-size:12px;line-height:1.45;color:var(--muted);margin-bottom:4px;} .facts dd {margin:0;font-size:16px;font-weight:600;font-variant-numeric:tabular-nums;} .basis {font-size:12px;line-height:1.55;color:var(--muted);margin:11px 0 12px;overflow-wrap:anywhere;}
details {border-top:1px solid var(--line);font-size:12px;line-height:1.6;color:var(--muted);padding:0;} summary {padding:13px 0;min-height:44px;cursor:pointer;color:var(--primary-text-color,#202124);font-size:13px;} details p {margin:0 0 12px;} a {color:var(--primary-color,#0277bd);text-underline-offset:3px;} .check-copy {grid-column:1 / -1;font-size:14px;line-height:1.6;margin:0;} .issue {padding:18px 0 6px;line-height:1.65;font-size:14px;}
.actions {display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:10px 24px 16px;} button {appearance:none;font:inherit;font-size:13px;font-weight:600;line-height:1.35;padding:11px 10px;min-height:44px;border:1px solid var(--line);border-radius:10px;background:transparent;color:var(--primary-text-color,#202124);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:7px;} button ha-icon {--mdc-icon-size:17px;flex-shrink:0;} button:hover:not(:disabled) {background:var(--secondary-background-color,#f3f4f6);} button:disabled {opacity:.55;cursor:default;} button.primary {background:var(--tint);border-color:transparent;color:var(--ink);} button.primary:hover:not(:disabled) {filter:brightness(.96);} button:focus-visible,summary:focus-visible,a:focus-visible {outline:2px solid var(--primary-color,#0277bd);outline-offset:3px;} .error {margin:0;padding:0 24px 16px;color:var(--error-color,#b00020);font-size:13px;line-height:1.5;} .feedback {margin:0;padding:0 24px 16px;color:var(--muted);font-size:12px;line-height:1.5;}
.contract {font-size:12px;line-height:1.6;color:var(--muted);margin:0 0 12px;} .record {display:grid;grid-template-columns:auto minmax(70px,1fr) auto;gap:10px;align-items:center;margin:0 24px 16px;} .record label {font-size:12px;color:var(--muted);} select {font:inherit;font-size:14px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#202124);border:1px solid var(--line);border-radius:8px;padding:10px;min-height:44px;} select:focus-visible {outline:2px solid var(--primary-color,#0277bd);outline-offset:3px;} .record-note {margin:0 24px 16px;font-size:11px;color:var(--muted);line-height:1.5;} @container(max-width:400px){.decision{display:block}.saving,.saving-label{text-align:left;max-width:none}.route{margin:0 0 12px}.record{margin-inline:18px;grid-template-columns:minmax(60px,1fr) auto}.record label{grid-column:1 / -1}.record-note{margin-inline:18px}} ::selection {background:var(--tint);color:var(--ink);} @container (max-width:360px) {header {padding:17px 18px 12px;} .decision {padding:19px 18px;} .verdict {font-size:25px;} .body {padding-left:18px;padding-right:18px;} .actions {padding-left:18px;padding-right:18px;gap:8px;} .facts {gap:10px;} button {font-size:12px;padding-left:7px;padding-right:7px;} }
`;

export class EnBWTariffCard extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); this._busy=false; this._error=''; this._feedback=''; this._recordBusy=false; this._selectedTariff=null; }
  setConfig(config) {
    if (!config.entity?.startsWith('sensor.')) throw new Error('EnBW Tarifcheck: entity muss ein Tarifwechsel-Sensor sein.');
    if (config.refresh_entity && !config.refresh_entity.startsWith('button.')) throw new Error('refresh_entity muss eine button-Entität sein.');
    if (config.language && !['de','en'].includes(config.language)) throw new Error('language: de oder en');
    this._config={...config}; this._signature=null; this._render();
  }
  set hass(value) { this._hass=value; this._render(); }
  getCardSize() { return 7; }
  getGridOptions() { return {columns:12,min_columns:6,rows:'auto'}; }
  static getStubConfig(hass) {
    const entity=Object.keys(hass.states).find(id=>id.startsWith('sensor.') && hass.states[id].attributes.basis==='three_complete_months_german_enbw_only' && !hass.states[id].attributes.unit_of_measurement);
    return {entity:entity || 'sensor.replace_with_tarifwechsel'};
  }
  _render() {
    if (!this._config || !this._hass) return;
    const state=this._hass.states[this._config.entity];
    const refresh=this._config.refresh_entity;
    const refreshState=refresh ? this._hass.states[refresh] : null;
    const dark=!!this._hass.themes?.darkMode;
    const de=(this._config.language || this._hass.locale?.language || this._hass.language || 'de').startsWith('de');
    const recordService=!!this._hass.services?.enbw_mobilityplus?.record_tariff_change;
    const signature=JSON.stringify([recordService,this._recordBusy,this._selectedTariff,state,refreshState?.state,dark,de,this._busy,this._error,this._feedback,this._config]);
    if (signature===this._signature) return;
    this._signature=signature;
    const d=tariffView(state), e=escapeHtml;
    const text=(g,en)=>de?g:en;
    const nf=new Intl.NumberFormat(de?'de-DE':'en-GB',{minimumFractionDigits:2,maximumFractionDigits:2});
    const number=n=>new Intl.NumberFormat(de?'de-DE':'en-GB',{maximumFractionDigits:1}).format(n);
    const money=n=>nf.format(n)+' €';
    const date=value=> {
      if (typeof value!=='string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return '—';
      const [y,m,day]=value.split('-'); return de?`${day}.${m}.${y}`:`${day}/${m}/${y}`;
    };
    const open=this.shadowRoot.querySelector('details')?.open;
    const focused=this.shadowRoot.activeElement?.dataset.action;
    const ja=d.change;
    const verdict=d.valid ? d.locked?text('Noch nicht wechseln','Wait before switching'):ja?text('Ja, wechseln','Yes, switch'):text('Nein, behalten','No, stay') : text('Bitte prüfen','Please check');
    const icon=d.locked?'mdi:calendar-clock':d.valid?ja?'mdi:check-circle-outline':'mdi:shield-check-outline':'mdi:alert-circle-outline';
    const fee=(f,p)=>typeof f==='number'&&typeof p==='number'&&Number.isFinite(f)&&Number.isFinite(p)?`${money(f)} ${text('Grundgebühr','base fee')} · ${number(p)} ct/kWh`:text('Grundgebühr enthalten','Including monthly fee');
    const reason={invalid_switch_dates:text('Bitte Wechselbeginn und nächsten Wechseltermin in den Integrationsoptionen korrigieren.','Correct the effective and next switch dates in the integration options.'),prices_outdated:text('Der Preisstand ist älter als 31 Tage. Bestätige die aktuellen Preise in den Integrationsoptionen.','Prices were last confirmed more than 31 days ago. Verify them in the integration options.'),invalid_prices:text('Bitte Tarif, Preise und Prüfdatum in den Integrationsoptionen prüfen.','Check the tariff, prices and verification date in the integration options.'),history_limit_reached:text('Die Abrufgrenze wurde erreicht. Erhöhe die Historiengrenze in den Integrationsoptionen.','The history limit was reached. Increase it in the integration options.'),insufficient_history:text('Für die Empfehlung fehlen drei vollständige Monate mit nachgewiesener Historienabdeckung.','Three complete months of covered history are needed.'),invalid_history:text('Die Historie enthält ungültige Daten. Bitte neu abrufen.','The history contains invalid data. Please refresh it.')};
    const problem=!state||['unknown','unavailable'].includes(state.state)||d.restored?text('Die Integration liefert gerade keine aktuellen Daten. Prüfe Verbindung und EnBW-Anmeldung.','Current integration data is unavailable. Check the connection and EnBW login.'):reason[d.reason]||text('Noch keine belastbare Empfehlung. Bitte Daten und Tarifpreise prüfen.','No reliable recommendation yet. Check the data and tariff prices.');
    const canRefresh=refreshState && !['unavailable','unknown'].includes(refreshState.state) && !this._busy;
    this.shadowRoot.innerHTML=`<style>${css}</style><ha-card><article class="card ${d.tone} ${dark?'dark':''}" aria-label="${text('EnBW Tarifvergleich','EnBW tariff comparison')}">
      <header><ha-icon icon="mdi:ev-station" aria-hidden="true"></ha-icon>${e(this._config.title||text('Dein EnBW-Tarifcheck','Your EnBW tariff check'))}</header>
      <section class="decision" aria-live="polite"><h2 class="verdict"><ha-icon icon="${icon}" aria-hidden="true"></ha-icon>${verdict}</h2>
      ${d.valid?`<p class="route">${ja?text(d.direction==='downgrade'?'Downgrade':'Upgrade',d.direction==='downgrade'?'Downgrade':'Upgrade')+`: <b>${d.current_tariff} → ${d.target_tariff}</b>`:text(`Tarif ${d.current_tariff} ist für deinen Verbrauch günstiger oder gleich teuer.`,`Tariff ${d.current_tariff} is cheaper or equal for your usage.`)}</p><div class="saving">${money(Math.abs(d.monthly_savings))}</div><p class="saving-label">${ja?d.locked?text('möglicher Vorteil ab '+date(d.next_switch_on),'potential saving from '+date(d.next_switch_on)):text('weniger pro Monat · Grundgebühren eingerechnet','less per month · monthly fees included'):text('monatlicher Vorteil deines Tarifs','monthly advantage of your current tariff')}</p>`:`<p class="check-copy">${e(problem)}</p>`}</section>
      <div class="body">${d.valid?`<table class="costs"><thead><tr><th>${text('Tarifvergleich','Tariff comparison')}</th><th>${text('pro Monat','per month')}</th></tr></thead><tbody>
      <tr class="${!ja?'best':''}"><td><span class="tariff">${e(d.current_tariff)} · ${text('aktuell','current')}</span><span class="sub">${fee(d.current_fee,d.current_price_ct)}</span></td><td><strong>${money(d.current_monthly_cost)}</strong></td></tr>
      <tr class="${ja?'best':''}"><td><span class="tariff">${e(d.target_tariff)} · ${text('Alternative','alternative')}</span><span class="sub">${fee(d.target_fee,d.target_price_ct)}</span></td><td><strong>${money(d.target_monthly_cost)}</strong></td></tr></tbody></table>
      <dl class="facts"><div><dt>${text('Ø EnBW-Ladung / Monat','Average EnBW usage / month')}</dt><dd>${number(d.average_energy)} kWh</dd></div><div><dt>${text('Alternative lohnt sich','Alternative pays off')}</dt><dd>${typeof d.break_even_kwh==='number'&&Number.isFinite(d.break_even_kwh)&&['above','below'].includes(d.threshold_relation)?`${d.threshold_relation==='above'?text('über','above'):text('unter','below')} ${number(d.break_even_kwh)} kWh`:text('siehe Kostenvergleich','see cost comparison')}</dd></div></dl>
      <p class="basis">${text('Basis','Based on')}: ${date(d.period_start)} – ${date(d.period_end)}<br>${text('Drei vollständige Monate · nur deutsche EnBW-Ladepunkte','Three complete months · German EnBW chargers only')}</p>`:`<p class="issue">${text('Es wird kein Ja oder Nein geraten. Sobald Daten und Preise wieder gültig sind, erscheint der Vergleich automatisch.','No decision is guessed. The comparison returns automatically when data and prices are valid.')}</p>`}
      <p class="contract">${text('Tarif gültig seit','Tariff effective since')}: <b>${date(d.tariff_started_on)}</b><br>${text('Nächster Wechsel möglich ab','Next switch available from')}: <b>${date(d.next_switch_on)}</b>${d.next_switch_on?'':text(' · bitte Termin eintragen',' · enter a date')}</p>
      <details ${open?'open':''}><summary>${text('Berechnung & Preisstand','Calculation & prices')}</summary><p>${text('Verbrauchsvergleich für kommende volle Tarifmonate. Roaming, identische Blockiergebühren, Guthaben und Sonderaktionen sind nicht eingerechnet. Dein Vertrag wird hier nicht geändert.','Usage comparison for future full tariff months. Excludes roaming, identical blocking fees, credit and promotions. Your contract is never changed here.')}</p><p>${text('Preise bestätigt','Prices verified')}: ${date(d.prices_checked)}. ${text('Preise werden manuell bestätigt, nicht automatisch von EnBW übernommen.','Prices require manual confirmation and are not automatically read from EnBW.')}</p><p><a href="https://www.enbw.com/elektromobilitaet/produkte/ladetarife" target="_blank" rel="noopener noreferrer">${text('Offizielle EnBW-Tarife','Official EnBW tariffs')}</a></p></details></div>
      <div class="actions"><button class="${!d.valid?'primary':''}" data-action="configure"><ha-icon icon="mdi:tune" aria-hidden="true"></ha-icon>${text('Tarif einstellen','Set tariff')}</button>${refresh?`<button class="${d.valid?'primary':''}" data-action="refresh" ${canRefresh?'':'disabled'} aria-busy="${this._busy}"><ha-icon icon="mdi:refresh" aria-hidden="true"></ha-icon>${this._busy?text('Wird geprüft …','Checking …'):text('Jetzt prüfen','Check now')}</button>`:''}</div>
      <div class="record"><label for="tariff">${text('Neuer Tarif','New tariff')}</label><select id="tariff" aria-label="${text('Heute gewählter Tarif','Tariff selected today')}" ${this._recordBusy?'disabled':''}>${['S','M','L'].map(t=>`<option value="${t}" ${(this._selectedTariff||d.current_tariff)===t?'selected':''}>${t}</option>`).join('')}</select><button data-action="record" ${!recordService||this._recordBusy?'disabled':''} aria-busy="${this._recordBusy}"><ha-icon icon="mdi:calendar-check" aria-hidden="true"></ha-icon>${this._recordBusy?text('Speichert …','Saving …'):text('Heute gewechselt','Switched today')}</button></div>
      <p class="record-note">${recordService?text('Merkt Tarif und heutiges Datum nur in HASS. Nächster Termin: ein Kalendermonat später, in den Optionen korrigierbar.','Records the tariff and today in HA only. Next date: one calendar month later; editable in options.'):text('Für die Schnellaktion die Integration aus main aktualisieren.','Update the integration from main to enable this action.')}</p>
      ${this._error?`<p class="error" role="alert">${e(this._error)}</p>`:''}${this._feedback?`<p class="feedback" role="status">${e(this._feedback)}</p>`:''}
      </article></ha-card>`;
    if (!refresh) this.shadowRoot.querySelector('.actions').style.gridTemplateColumns='1fr';
    this.shadowRoot.querySelector('[data-action="configure"]').onclick=()=>{history.pushState(null,'','/config/integrations/integration/enbw_mobilityplus'); window.dispatchEvent(new Event('location-changed'));};
    const button=this.shadowRoot.querySelector('[data-action="refresh"]');
    if (button) button.onclick=async()=>{
      if (this._busy || !canRefresh) return;
      this._busy=true; this._error=''; this._feedback=''; this._render();
      try { await this._hass.callService('button','press',{entity_id:refresh}); this._feedback=text('Prüfung abgeschlossen. Die Karte zeigt den aktuellen Vergleich.','Check completed. The card shows the current comparison.'); }
      catch { this._error=text('Aktualisierung fehlgeschlagen. Bitte EnBW-Anmeldung und Verbindung prüfen.','Refresh failed. Check the EnBW login and connection.'); }
      finally { this._busy=false; this._render(); }
    };
    this.shadowRoot.querySelector('#tariff').onchange=event=>{this._selectedTariff=event.target.value;};
    this.shadowRoot.querySelector('[data-action="record"]').onclick=async()=>{
      if (!recordService || this._recordBusy) return;
      const tariff=this.shadowRoot.querySelector('#tariff').value;
      this._recordBusy=true;this._error='';this._feedback='';this._selectedTariff=tariff;this._render();
      const data={tariff};if(d.config_entry_id)data.config_entry_id=d.config_entry_id;
      try {await this._hass.callService('enbw_mobilityplus','record_tariff_change',data);this._feedback=text('Tarifwechsel zu '+tariff+' für heute gespeichert.','Recorded today’s switch to '+tariff+'.');}
      catch {this._error=text('Tarifwechsel konnte nicht gespeichert werden. Bitte Integration und Kontoauswahl prüfen.','Could not record the change. Check the integration and account selection.');}
      finally {this._recordBusy=false;this._render();}
    };
    if (focused) this.shadowRoot.querySelector(`[data-action="${focused}"]`)?.focus({preventScroll:true});
  }
}
if (!customElements.get('enbw-tariff-card')) customElements.define('enbw-tariff-card',EnBWTariffCard);
window.customCards=window.customCards||[];
if (!window.customCards.some(c=>c.type==='enbw-tariff-card')) window.customCards.push({type:'enbw-tariff-card',name:'EnBW Tarifcheck',description:'S/M/L: Ja/Nein, Upgrade, Downgrade und monatliche Ersparnis.',preview:true});
