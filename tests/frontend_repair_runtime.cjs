// Execute real display functions against a small DOM stub; no tax formulas copied.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const elements = new Map();
const requestedIds = new Set();
function element() {
  let text = '', html = '';
  const children = [], listeners = new Map();
  return {
    hidden: true, disabled: false, className: '', style: {}, value: '', children,
    set textContent(value) { text = String(value); html = text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'); },
    get textContent() { return text; },
    set innerHTML(value) { html = String(value); children.length = 0; }, get innerHTML() { return html; },
    appendChild(child) { children.push(child); return child; },
    addEventListener(type, listener) { listeners.set(type, listener); },
    dispatch(type) { listeners.get(type)?.({target: this}); },
    querySelectorAll(selector) { return selector === 'input' ? children.filter(child => child.type === 'input') : []; },
  };
}
const document = {
  addEventListener() {}, createElement: element,
  querySelectorAll(selector) { assert.equal(selector, 'input[name="regions"]:checked'); return [{value:'GB'}, {value:'SG'}]; },
  getElementById(id) { requestedIds.add(id); if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
};
const context = vm.createContext({document, console, Intl, Number, String, Math});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js/app.js'), 'utf8'), context);
context.updateSummaryCard({total_tax:'13449', total_statutory_deductions:'21099',
  net_income:'78901', total_income:'100000', effective_rate:'.13449',
  statutory_effective_rate:'.21099', marginal_rate:'.22', balance_due:'13449'});
assert.match(elements.get('total-tax-display').textContent, /21,099/);
assert.match(elements.get('net-income-display').textContent, /78,901/);
assert.match(elements.get('effective-rate-display').textContent, /21\.1/);
assert.equal(elements.get('tax-status-badge').textContent, 'Modelled Taxes + Contributions');
context.updateSummaryCard({total_modelled_deductions:-78.5, net_income:1078.5,
  total_income:1000, statutory_effective_rate:-.0785, marginal_rate:0, balance_due:-155});
assert.equal(elements.get('tax-status-badge').textContent, 'Net Modelled Credit');
context.populateFICABreakdown({summary:{total_income:'100000', employee_social_security_tax:'0', employee_medicare_tax:'0', employee_payroll_tax:'0'}});
assert.match(elements.get('fica-total-amount').textContent, /\$0/);
context.populateLocalBreakdown({summary:{total_local_tax:'3120'}, local:[{
  jurisdiction_name:'NYC <unsafe>', total_tax:'3120', withholding:'3500', balance_due_or_refund:'-380'}]});
assert.equal(elements.get('local-breakdown-section').hidden, false);
assert.match(elements.get('local-breakdown-content').innerHTML, /&lt;unsafe&gt;/);
assert.match(elements.get('local-breakdown-content').innerHTML, /3,500/);
const modal = context.buildUSBreakdownModalContent({gross_income_local:100000, total_tax_local:21099,
  effective_rate:.21099, us_breakdown:{federal_tax:13449, federal_ordinary_tax:13449,
  federal_taxable_income:84250, federal_effective_rate:.13449, employee_payroll_tax:7650,
  state_name:'Texas', state_tax:0, has_state_income_tax:false}}, 'USD');
assert.match(modal, /7,650/);
assert.ok(modal.indexOf('Employee payroll tax') > modal.indexOf('Total Federal Tax'));
const waModal = context.buildUSBreakdownModalContent({gross_income_local:300000, total_tax_local:30000,
  us_breakdown:{state_name:'Washington', state_tax:1540, has_state_income_tax:false,
    state_details:{tax_type:'capital_gains_excise', state_taxable_income:22000, tax_before_credits:1540, total_state_tax:1540}}}, 'USD');
assert.match(waModal, /1,540/);
assert.match(waModal, /Capital gains excise base/);
assert.match(waModal, /Capital gains excise base<\/span><span>\$22,000/);
assert.match(context.buildJurisdictionReconciliation({taxable_income:12000}), /Taxable income<\/span><span>\$12,000/);
assert.match(context.buildJurisdictionReconciliation({taxable_income:0, state_taxable_income:12000}), /Taxable income<\/span><span>\$0/);
assert.doesNotMatch(waModal, /has no state income tax/);
assert.match(waModal, /Net tax \/ \(refundable credit\)<\/span><span>\$1,540/);
const refund = context.buildJurisdictionReconciliation({tax_before_credits:0, total_tax:-63,
  credits:[{credit_name:'School credit', amount_used:63, is_refundable:true}]});
assert.match(refund, /School credit \(refundable\)/);
assert.match(refund, /-\$63/);
const apiRefund = context.buildJurisdictionReconciliation({taxable_income:0, tax_before_credits:0, total_tax:-63,
  credits:[{code:'NYC-SCHOOL', name:'School credit', amount:63, refundable:true}]});
assert.match(apiRefund, /School credit \(refundable\)<\/span><span>-\$63/);
const apiLimitedCredit = context.buildJurisdictionReconciliation({tax_before_credits:100, total_tax:0,
  credits:[{code:'LIMITED', name:'Limited credit', amount:100, refundable:false}]});
assert.match(apiLimitedCredit, /Limited credit<\/span><span>-\$100/);
assert.doesNotMatch(apiLimitedCredit, /Limited credit \(refundable\)/);
context.populateStateBreakdown([{jurisdiction_name:'Offset state', tax_before_credits:100, total_tax:0,
  total_credits:100, credits:[{credit_name:'Offset credit', amount_used:100, is_refundable:false}]}]);
assert.match(elements.get('state-breakdown-content').innerHTML, /Offset credit/);
vm.runInContext('errorSection = document.getElementById("error-section")', context);
context.showError({error:{message:'Tax calculation failed', details:[{message:'Philadelphia requires philly_first_half_wages'}]}});
assert.match(elements.get('error-message').textContent, /philly_first_half_wages/);
const assumptions = context.buildCompareAssumptionsHtml([{region_name:'Canada <unsafe>', notes:[
  "Domestic profile used (CA): {'province': 'ON'}", 'unrelated note']}]);
assert.match(assumptions, /province.*ON/);
assert.match(assumptions, /Canada &lt;unsafe&gt;/);
assert.match(assumptions, /Home-country tax, treaties and living costs are excluded/);
assert.doesNotMatch(assumptions, /unrelated note/);
requestedIds.clear();
function input(id, value) { document.getElementById(id).value = String(value); }
for (const prefix of ['intl', 'compare']) {
  input(`${prefix}-tax-year`, 2025);
  input(`${prefix}-wages`, 100000);
  input(`${prefix}-ltcg`, 2000);
  input(`${prefix}-gb-region`, 'scotland');
  input(`${prefix}-sg-citizen`, 'false');
}
input('intl-country', 'GB');
assert.equal(context.gatherIncomeBreakdown('intl').employment_wages, 100000);
let payload = context.gatherIntlFormData();
assert.equal(payload.gross_income, 102000);
assert.equal(payload.income.capital_gains_long_term, 2000);
assert.equal(payload.uk.tax_region, 'scotland');
assert.equal(payload.currency_code, 'GBP');
input('intl-country', 'SG');
assert.equal(context.gatherIntlFormData().sg.is_citizen_or_pr, false);
input('compare-currency', 'USD');
input('compare-filing-status', 'single');
payload = context.gatherCompareFormData();
assert.equal(payload.gross_income, 102000);
assert.equal(payload.income.employment_wages, 100000);
assert.equal(payload.country_profiles.GB.tax_region, 'scotland');
assert.equal(payload.country_profiles.SG.is_citizen_or_pr, false);
input('tax-year', 2025);
input('filing-status', 'single');
input('residence-state', 'NY');
input('residence-zip', '10001');
input('local-withholding', 3500);
payload = context.gatherFormData();
assert.equal(payload.residency.residence_zip, '10001');
assert.equal(payload.income.wages[0].local_withholding, 3500);
assert.equal(payload.filer.age_at_year_end, 40);
input('dividends', 1000);
input('qualified-dividends', 600);
input('us-az-eligible-ltcg', 0);
payload = context.gatherFormData();
assert.equal(payload.income.dividends.ordinary, 1000);
assert.equal(payload.income.dividends.qualified, 600);
assert.equal(payload.us_scenario.az_post_2011_eligible_long_term_gains, undefined);
assert.equal(payload.us_scenario.philly_first_half_wages, undefined);
input('residence-state', 'AZ');
payload = context.gatherFormData();
assert.equal(payload.us_scenario.az_post_2011_eligible_long_term_gains, 0);
input('residence-state', 'PA');
input('residence-zip', '19103-1234');
input('us-philly-first-half-wages', 50000);
payload = context.gatherFormData();
assert.equal(payload.us_scenario.az_post_2011_eligible_long_term_gains, undefined);
assert.equal(payload.us_scenario.philly_first_half_wages, undefined);
assert.equal(payload.residency.local_jurisdiction_id, undefined);
input('residence-local-jurisdiction', 'US-PA-PHL');
payload = context.gatherFormData();
assert.equal(payload.us_scenario.philly_first_half_wages, 50000);
assert.equal(payload.residency.local_jurisdiction_id, 'US-PA-PHL');
input('compare-az-eligible-ltcg', 0);
input('compare-philly-first-half-wages', 50000);
assert.equal(context.gatherUSScenarioFacts('compare', ['US-TX']).az_post_2011_eligible_long_term_gains, undefined);
assert.equal(context.gatherUSScenarioFacts('compare', ['US-AZ']).az_post_2011_eligible_long_term_gains, 0);
assert.equal(context.gatherUSScenarioFacts('compare', ['US-PA-PHL']).philly_first_half_wages, 50000);
const stateSelect = elements.get('residence-state');
const localSelect = elements.get('residence-local-jurisdiction');
const phillyFacts = document.getElementById('us-philly-facts');
for (const id of ['us-philly-six-month-gains', 'us-philly-first-half-wages']) {
  const field = elements.get(id);
  field.type = 'input';
  phillyFacts.appendChild(field);
}
localSelect.value = '';
context.setupResidenceLocationSelector();
context.setCoveredUSCities([
  {region_id: 'US-PA-PHL', state_code: 'PA', display_name: 'Philadelphia, PA'},
  {region_id: 'US-NY-NYC', state_code: 'NY', display_name: 'New York City, NY'},
]);
stateSelect.value = 'PA';
stateSelect.dispatch('change');
assert.equal(localSelect.disabled, false);
assert.deepEqual(localSelect.children.map(option => option.value), ['', 'US-PA-PHL']);
localSelect.value = 'US-PA-PHL';
localSelect.dispatch('change');
assert.equal(elements.get('us-philly-facts').hidden, false);
input('us-philly-six-month-gains', 2000);
input('us-philly-first-half-wages', 50000);
stateSelect.value = 'NY';
stateSelect.dispatch('change');
assert.equal(localSelect.value, '');
assert.deepEqual(localSelect.children.map(option => option.value), ['', 'US-NY-NYC']);
assert.equal(elements.get('us-philly-facts').hidden, true);
assert.equal(elements.get('us-philly-first-half-wages').value, '');
assert.equal(elements.get('us-philly-six-month-gains').value, '');
const html = fs.readFileSync(path.join(__dirname, '../static/index.html'), 'utf8');
for (const id of requestedIds) assert.ok(html.includes(`id="${id}"`), `Missing real form element: ${id}`);
console.log('Frontend runtime contracts passed');
