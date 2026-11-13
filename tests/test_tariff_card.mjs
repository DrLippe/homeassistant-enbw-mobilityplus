// Browser-independent guard tests: never show a confident verdict for bad data.
import assert from 'node:assert/strict';
import fs from 'node:fs';
globalThis.HTMLElement=class {};
globalThis.customElements={get:()=>true};
globalThis.window={customCards:[]};
const source=fs.readFileSync(new URL('../custom_components/enbw_mobilityplus/www/enbw-tariff-card.js',import.meta.url),'utf8');
const {tariffView}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const a={monthly_savings:5,current_monthly_cost:80,target_monthly_cost:75,average_energy:160,current_tariff:'M',target_tariff:'L'};
const scenarios=[['Ja',a,'yes'],['Nein',{...a,monthly_savings:-5},'no'],['Nein',{...a,monthly_savings:0},'no'],['Prüfen',a,'check'],['unavailable',a,'check'],['unknown',a,'check'],['Ja',{...a,monthly_savings:null},'check'],['Ja',{...a,monthly_savings:NaN},'check'],['Ja',{...a,restored:true},'check'],['Ja',{...a,current_tariff:'<script>'},'check'],['Ja',{...a,monthly_savings:0},'check'],['Nein',a,'check'],['Ja',{...a,average_energy:-1},'check'],['Ja',{...a,target_monthly_cost:Infinity},'check']];
for(const [state,attributes,tone] of scenarios) assert.equal(tariffView({state,attributes}).tone,tone);
assert.equal(tariffView({...{state:'Ja'},attributes:{...a,switch_allowed:false,next_switch_on:'2026-12-06'}}).tone,'wait');
assert.equal(tariffView({...{state:'Ja'},attributes:{...a,switch_allowed:true,next_switch_on:'2026-12-06'}}).tone,'yes');
assert.equal(tariffView(undefined).valid,false);
console.log(`${scenarios.length+3} tariff-card guard checks passed`);
