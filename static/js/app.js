/**
 * TaxEstimate - Frontend Application
 *
 * Pure vanilla JavaScript - no frameworks, no build step
 *
 * DISCLAIMER: This application is for estimation purposes only
 * and does not constitute tax advice.
 */

// =============================================================================
// Constants
// =============================================================================

const API_BASE = '/v1';

// Current mode: 'us', 'intl', or 'compare'
let currentMode = 'us';

// Region information for display (countries + US states/cities)
const REGION_NAMES = {
    // International countries
    'GB': 'United Kingdom',
    'DE': 'Germany',
    'FR': 'France',
    'SG': 'Singapore',
    'HK': 'Hong Kong',
    'AE': 'UAE (Dubai)',
    'JP': 'Japan',
    'AU': 'Australia',
    'CA': 'Canada',
    'IT': 'Italy',
    'ES': 'Spain',
    'PT': 'Portugal',
};

// Alias for backward compatibility
const COUNTRY_NAMES = REGION_NAMES;

// No income tax US states
const NO_TAX_US_STATES = ['AK', 'FL', 'NV', 'SD', 'TN', 'TX', 'WA', 'WY'];

// Maximum regions for comparison
const MAX_COMPARISON_REGIONS = 6;

const CURRENCY_SYMBOLS = {
    'USD': '$',
    'GBP': '\u00a3',
    'EUR': '\u20ac',
    'SGD': 'S$',
    'HKD': 'HK$',
    'AED': 'AED',
    'JPY': '\u00a5',
    'AUD': 'A$',
    'CAD': 'C$'
};

// =============================================================================
// Tax Configuration Constants
// =============================================================================

// Social Security wage base by year (source: IRS)
// These values should ideally come from the API, but are defined here as fallback
const SS_WAGE_BASE = {
    2025: 176100,
    2024: 168600,
    2023: 160200
};

// =============================================================================
// Security Helpers
// =============================================================================

/**
 * Escape HTML special characters to prevent XSS attacks.
 * Use this function when inserting untrusted text into HTML templates.
 * @param {string} text - The text to escape
 * @returns {string} The escaped text safe for HTML insertion
 */
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
    const str = String(text);
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

const COUNTRY_CURRENCIES = {
    'GB': 'GBP',
    'DE': 'EUR',
    'FR': 'EUR',
    'SG': 'SGD',
    'HK': 'HKD',
    'AE': 'AED',
    'JP': 'JPY',
    'AU': 'AUD',
    'CA': 'CAD',
    'IT': 'EUR',
    'ES': 'EUR',
    'PT': 'EUR'
};

// US States with their codes
const US_STATES = [
    { code: 'AL', name: 'Alabama' },
    { code: 'AK', name: 'Alaska' },
    { code: 'AZ', name: 'Arizona' },
    { code: 'AR', name: 'Arkansas' },
    { code: 'CA', name: 'California' },
    { code: 'CO', name: 'Colorado' },
    { code: 'CT', name: 'Connecticut' },
    { code: 'DE', name: 'Delaware' },
    { code: 'DC', name: 'District of Columbia' },
    { code: 'FL', name: 'Florida' },
    { code: 'GA', name: 'Georgia' },
    { code: 'HI', name: 'Hawaii' },
    { code: 'ID', name: 'Idaho' },
    { code: 'IL', name: 'Illinois' },
    { code: 'IN', name: 'Indiana' },
    { code: 'IA', name: 'Iowa' },
    { code: 'KS', name: 'Kansas' },
    { code: 'KY', name: 'Kentucky' },
    { code: 'LA', name: 'Louisiana' },
    { code: 'ME', name: 'Maine' },
    { code: 'MD', name: 'Maryland' },
    { code: 'MA', name: 'Massachusetts' },
    { code: 'MI', name: 'Michigan' },
    { code: 'MN', name: 'Minnesota' },
    { code: 'MS', name: 'Mississippi' },
    { code: 'MO', name: 'Missouri' },
    { code: 'MT', name: 'Montana' },
    { code: 'NE', name: 'Nebraska' },
    { code: 'NV', name: 'Nevada' },
    { code: 'NH', name: 'New Hampshire' },
    { code: 'NJ', name: 'New Jersey' },
    { code: 'NM', name: 'New Mexico' },
    { code: 'NY', name: 'New York' },
    { code: 'NC', name: 'North Carolina' },
    { code: 'ND', name: 'North Dakota' },
    { code: 'OH', name: 'Ohio' },
    { code: 'OK', name: 'Oklahoma' },
    { code: 'OR', name: 'Oregon' },
    { code: 'PA', name: 'Pennsylvania' },
    { code: 'RI', name: 'Rhode Island' },
    { code: 'SC', name: 'South Carolina' },
    { code: 'SD', name: 'South Dakota' },
    { code: 'TN', name: 'Tennessee' },
    { code: 'TX', name: 'Texas' },
    { code: 'UT', name: 'Utah' },
    { code: 'VT', name: 'Vermont' },
    { code: 'VA', name: 'Virginia' },
    { code: 'WA', name: 'Washington' },
    { code: 'WV', name: 'West Virginia' },
    { code: 'WI', name: 'Wisconsin' },
    { code: 'WY', name: 'Wyoming' }
];

// =============================================================================
// DOM Elements
// =============================================================================

let form;
let intlForm;
let compareForm;
let resultsSection;
let intlResultsSection;
let compareResultsSection;
let errorSection;
let loadingSection;

// =============================================================================
// Initialization
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Cache DOM elements
    form = document.getElementById('tax-form');
    intlForm = document.getElementById('intl-form');
    compareForm = document.getElementById('compare-form');
    resultsSection = document.getElementById('results');
    intlResultsSection = document.getElementById('intl-results');
    compareResultsSection = document.getElementById('compare-results');
    errorSection = document.getElementById('error');
    loadingSection = document.getElementById('loading');

    // Populate state dropdown
    populateStates();

    // Setup event listeners
    form.addEventListener('submit', handleFormSubmit);

    // Setup international form
    if (intlForm) {
        intlForm.addEventListener('submit', handleIntlFormSubmit);
    }

    // Setup compare form
    if (compareForm) {
        compareForm.addEventListener('submit', handleCompareFormSubmit);
    }

    // Setup mode toggle
    setupModeToggle();

    // Setup country selector currency hint
    setupCountrySelector();

    // Load comparison regions (US states, cities, international)
    loadComparisonRegions();

    // Setup region selection limit tracking
    setupRegionSelectionTracking();

    // Setup live total income counters
    setupIncomeTotals();

    // Setup region search filtering
    setupRegionSearch();

    const errorDismissBtn = document.getElementById('error-dismiss');
    if (errorDismissBtn) {
        errorDismissBtn.addEventListener('click', hideError);
    }
});

// =============================================================================
// Mode Toggle
// =============================================================================

function setupModeToggle() {
    const modeUsBtn = document.getElementById('mode-us');
    const modeIntlBtn = document.getElementById('mode-intl');
    const modeCompareBtn = document.getElementById('mode-compare');

    if (modeUsBtn) {
        modeUsBtn.addEventListener('click', () => switchMode('us'));
    }
    if (modeIntlBtn) {
        modeIntlBtn.addEventListener('click', () => switchMode('intl'));
    }
    if (modeCompareBtn) {
        modeCompareBtn.addEventListener('click', () => switchMode('compare'));
    }
}

function switchMode(mode) {
    currentMode = mode;

    // Update button states
    const buttons = document.querySelectorAll('.mode-btn');
    buttons.forEach(btn => btn.classList.remove('active'));

    const activeBtn = document.getElementById(`mode-${mode}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }

    // Show/hide forms
    if (form) form.hidden = (mode !== 'us');
    if (intlForm) intlForm.hidden = (mode !== 'intl');
    if (compareForm) compareForm.hidden = (mode !== 'compare');

    // Hide all results
    hideAllResults();
    hideError();
}

function hideAllResults() {
    if (resultsSection) resultsSection.hidden = true;
    if (intlResultsSection) intlResultsSection.hidden = true;
    if (compareResultsSection) compareResultsSection.hidden = true;
}

// =============================================================================
// Country Selector
// =============================================================================

function setupCountrySelector() {
    const countrySelect = document.getElementById('intl-country');
    const currencyHint = document.getElementById('currency-hint');

    if (countrySelect && currencyHint) {
        countrySelect.addEventListener('change', () => {
            const countryCode = countrySelect.value;
            if (countryCode && COUNTRY_CURRENCIES[countryCode]) {
                const currency = COUNTRY_CURRENCIES[countryCode];
                const symbol = CURRENCY_SYMBOLS[currency] || currency;
                currencyHint.textContent = `Enter amount in ${currency} (${symbol})`;
            } else {
                currencyHint.textContent = 'Enter amount in local currency';
            }
        });
    }
}

// =============================================================================
// Comparison Region Loading
// =============================================================================

/**
 * Load US states and cities from API and populate checkboxes.
 */
async function loadComparisonRegions() {
    try {
        const response = await fetch(`${API_BASE}/comparison/regions`);
        if (!response.ok) {
            console.warn('Failed to load comparison regions:', response.status);
            return;
        }

        const data = await response.json();

        // Populate US states
        populateUSStates(data.us_states || []);

        // Populate US cities
        populateUSCities(data.us_cities || []);

        // Update region names map with loaded data
        updateRegionNames(data);

    } catch (err) {
        console.warn('Error loading comparison regions:', err);
        // Fallback: show error message in grids
        const statesGrid = document.getElementById('us-states-grid');
        const citiesGrid = document.getElementById('us-cities-grid');
        if (statesGrid) {
            statesGrid.innerHTML = '<span class="loading-text">Failed to load US states</span>';
        }
        if (citiesGrid) {
            citiesGrid.innerHTML = '<span class="loading-text">Failed to load US cities</span>';
        }
    }
}

/**
 * Populate US states checkboxes.
 */
function populateUSStates(states) {
    const grid = document.getElementById('us-states-grid');
    if (!grid) return;

    // Clear loading text
    grid.innerHTML = '';

    // Sort: popular states first, then alphabetically
    const popularStates = ['US-CA', 'US-TX', 'US-FL', 'US-NY', 'US-WA', 'US-NV'];
    const sortedStates = states.sort((a, b) => {
        const aPopular = popularStates.includes(a.region_id);
        const bPopular = popularStates.includes(b.region_id);
        if (aPopular && !bPopular) return -1;
        if (!aPopular && bPopular) return 1;
        return a.name.localeCompare(b.name);
    });

    sortedStates.forEach(state => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.name = 'regions';
        checkbox.value = state.region_id;

        // Pre-check California and Texas for demo
        if (state.region_id === 'US-CA' || state.region_id === 'US-TX') {
            checkbox.checked = true;
        }

        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(` ${state.name} (${state.abbreviation})`));

        // Add "No tax" badge for states without income tax
        if (!state.has_income_tax) {
            const badge = document.createElement('span');
            badge.className = 'no-tax-badge';
            badge.textContent = 'No tax';
            label.appendChild(badge);
        }

        grid.appendChild(label);
    });

    // Update count in section header
    const countSpan = document.querySelector('#us-states-section .region-count');
    if (countSpan) {
        countSpan.textContent = `(${states.length})`;
    }
}

/**
 * Populate US cities checkboxes.
 */
function populateUSCities(cities) {
    const grid = document.getElementById('us-cities-grid');
    if (!grid) return;

    // Clear loading text
    grid.innerHTML = '';

    cities.forEach(city => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.name = 'regions';
        checkbox.value = city.region_id;

        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(` ${city.display_name}`));

        grid.appendChild(label);
    });

    // Update count in section header
    const countSpan = document.querySelector('#us-cities-section .region-count');
    if (countSpan) {
        countSpan.textContent = `(${cities.length})`;
    }
}

/**
 * Update the REGION_NAMES map with loaded data.
 */
function updateRegionNames(data) {
    // Add US states
    (data.us_states || []).forEach(state => {
        REGION_NAMES[state.region_id] = `${state.name}, USA`;
    });

    // Add US cities
    (data.us_cities || []).forEach(city => {
        REGION_NAMES[city.region_id] = city.display_name;
    });

    // Add international (in case they weren't already there)
    (data.international || []).forEach(country => {
        REGION_NAMES[country.region_id] = country.name;
    });
}

/**
 * Setup selection tracking for region checkboxes.
 */
function setupRegionSelectionTracking() {
    const compareForm = document.getElementById('compare-form');
    if (!compareForm) return;

    // Use event delegation to handle checkbox changes
    compareForm.addEventListener('change', (event) => {
        if (event.target.type === 'checkbox' && event.target.name === 'regions') {
            updateSelectionCount();
            enforceSelectionLimit(event.target);
            updateChips();
        }
    });

    // Initial count update
    updateSelectionCount();
    updateChips();
}

/**
 * Update the selection count display.
 */
function updateSelectionCount() {
    const countSpan = document.getElementById('selection-count');
    if (!countSpan) return;

    const selected = document.querySelectorAll('input[name="regions"]:checked').length;
    countSpan.textContent = selected;

    // Update styling based on count
    countSpan.classList.remove('selection-limit-reached', 'selection-limit-exceeded');
    if (selected === MAX_COMPARISON_REGIONS) {
        countSpan.classList.add('selection-limit-reached');
    } else if (selected > MAX_COMPARISON_REGIONS) {
        countSpan.classList.add('selection-limit-exceeded');
    }

    const badge = document.getElementById('selection-count-badge');
    if (badge) {
        badge.classList.remove('badge-warning', 'badge-limit');
        if (selected >= MAX_COMPARISON_REGIONS) {
            badge.classList.add('badge-limit');
        } else if (selected >= MAX_COMPARISON_REGIONS - 1) {
            badge.classList.add('badge-warning');
        }
    }
}

/**
 * Enforce maximum selection limit.
 */
function enforceSelectionLimit(changedCheckbox) {
    const selected = document.querySelectorAll('input[name="regions"]:checked');

    if (selected.length > MAX_COMPARISON_REGIONS && changedCheckbox.checked) {
        // Uncheck the just-checked checkbox
        changedCheckbox.checked = false;
        updateSelectionCount();
        updateChips();
        alert(`Maximum ${MAX_COMPARISON_REGIONS} regions can be compared at once.`);
    }
}

/**
 * Update the selected region chips display.
 */
function updateChips() {
    const container = document.getElementById('selected-chips');
    if (!container) return;

    container.innerHTML = '';
    const checked = document.querySelectorAll('input[name="regions"]:checked');

    checked.forEach(cb => {
        const label = cb.closest('label');
        const name = label ? label.textContent.trim() : cb.value;

        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.innerHTML = `${escapeHtml(name)} <button type="button" class="chip-remove" aria-label="Remove ${escapeHtml(name)}">&times;</button>`;

        chip.querySelector('button').addEventListener('click', () => {
            cb.checked = false;
            updateSelectionCount();
            updateChips();
        });

        container.appendChild(chip);
    });
}

// =============================================================================
// Live Total Income Counters
// =============================================================================

/**
 * Setup live total income display for each form group.
 */
function setupIncomeTotals() {
    ['us', 'intl', 'compare'].forEach(group => {
        const inputs = document.querySelectorAll(`input[data-income-group="${group}"]`);
        const displayEl = document.getElementById(`${group}-total-income-value`);
        if (!displayEl || inputs.length === 0) return;

        const updateTotal = () => {
            let total = 0;
            inputs.forEach(input => {
                total += parseFloat(input.value) || 0;
            });
            if (group === 'us') {
                displayEl.textContent = formatCurrency(total);
            } else {
                displayEl.textContent = formatNumber(total);
            }
        };

        inputs.forEach(input => {
            input.addEventListener('input', updateTotal);
        });
        updateTotal();
    });
}

// =============================================================================
// Region Search Filtering
// =============================================================================

/**
 * Setup search/filter for region checkboxes in the compare form.
 */
function setupRegionSearch() {
    const searchInput = document.getElementById('region-search');
    if (!searchInput) return;

    searchInput.addEventListener('input', () => {
        const query = searchInput.value.toLowerCase().trim();
        const labels = document.querySelectorAll('#compare-form .checkbox-grid label');

        labels.forEach(label => {
            const text = label.textContent.toLowerCase();
            label.style.display = query === '' || text.includes(query) ? '' : 'none';
        });
    });
}

// =============================================================================
// State Dropdown
// =============================================================================

function populateStates() {
    const stateSelect = document.getElementById('residence-state');
    if (!stateSelect) return;

    // Add states to dropdown
    US_STATES.forEach(state => {
        const option = document.createElement('option');
        option.value = state.code;
        option.textContent = `${state.name} (${state.code})`;
        stateSelect.appendChild(option);
    });
}

// =============================================================================
// Form Handling
// =============================================================================

async function handleFormSubmit(e) {
    e.preventDefault();
    await calculateTaxes();
}

async function handleIntlFormSubmit(e) {
    e.preventDefault();
    await calculateInternationalTaxes();
}

async function handleCompareFormSubmit(e) {
    e.preventDefault();
    await calculateComparison();
}

function gatherFormData() {
    const taxYear = parseInt(document.getElementById('tax-year').value, 10);
    const filingStatus = document.getElementById('filing-status').value;
    const residenceState = document.getElementById('residence-state').value;

    const wages = parseFloat(document.getElementById('wages').value) || 0;
    const federalWithholding = parseFloat(document.getElementById('federal-withholding').value) || 0;
    const stateWithholding = parseFloat(document.getElementById('state-withholding').value) || 0;
    const interest = parseFloat(document.getElementById('interest').value) || 0;
    const dividends = parseFloat(document.getElementById('dividends').value) || 0;
    const longTermCapGains = parseFloat(document.getElementById('ltcg').value) || 0;
    const shortTermCapGains = parseFloat(document.getElementById('stcg').value) || 0;

    // Build the EstimateRequest object matching the API schema
    const request = {
        tax_year: taxYear,
        filer: {
            filing_status: filingStatus
        },
        residency: {
            residence_state: residenceState
        },
        income: {}
    };

    // Only include wages if there's income
    if (wages > 0 || federalWithholding > 0 || stateWithholding > 0) {
        request.income.wages = [{
            employer_name: 'Primary Employer',
            employer_state: residenceState,
            gross_wages: wages,
            federal_withholding: federalWithholding,
            state_withholding: stateWithholding
        }];
    }

    // Only include interest if there's income
    if (interest > 0) {
        request.income.interest = {
            taxable: interest
        };
    }

    // Only include dividends if there's income
    if (dividends > 0) {
        request.income.dividends = {
            ordinary: dividends
        };
    }

    // Only include capital gains if there's income
    if (longTermCapGains > 0 || shortTermCapGains > 0) {
        request.income.capital_gains = {
            long_term_gain: longTermCapGains,
            short_term_gain: shortTermCapGains
        };
    }

    return request;
}

// =============================================================================
// API Communication
// =============================================================================

async function calculateTaxes() {
    // Validate form
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const formData = gatherFormData();

    // Show loading, hide results and error
    showLoading();
    hideResults();
    hideError();

    try {
        const response = await fetch(`${API_BASE}/estimates`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch {
                errorData = { error: { message: `HTTP ${response.status}: ${response.statusText}` } };
            }
            showError(errorData);
            return;
        }

        const result = await response.json();
        displayResults(result);
    } catch (err) {
        showError({
            error: {
                message: 'Network error. Please check your connection and try again.'
            }
        });
    } finally {
        hideLoading();
    }
}

// =============================================================================
// Income Breakdown Helper
// =============================================================================

/**
 * Gather income breakdown fields from form inputs.
 * @param {string} prefix - The field ID prefix (e.g., 'intl', 'compare')
 * @returns {object} Income breakdown object for API request
 */
function gatherIncomeBreakdown(prefix) {
    return {
        employment_wages: parseFloat(document.getElementById(`${prefix}-wages`)?.value) || 0,
        capital_gains_long_term: parseFloat(document.getElementById(`${prefix}-ltcg`)?.value) || 0,
        capital_gains_short_term: parseFloat(document.getElementById(`${prefix}-stcg`)?.value) || 0,
        dividends_qualified: parseFloat(document.getElementById(`${prefix}-qual-div`)?.value) || 0,
        dividends_ordinary: parseFloat(document.getElementById(`${prefix}-ord-div`)?.value) || 0,
        interest: parseFloat(document.getElementById(`${prefix}-interest`)?.value) || 0,
        self_employment: parseFloat(document.getElementById(`${prefix}-self-emp`)?.value) || 0,
        rental: parseFloat(document.getElementById(`${prefix}-rental`)?.value) || 0,
    };
}

/**
 * Calculate total income from breakdown object.
 * @param {object} breakdown - Income breakdown object
 * @returns {number} Total income
 */
function calculateTotalIncome(breakdown) {
    return (
        breakdown.employment_wages +
        breakdown.capital_gains_long_term +
        breakdown.capital_gains_short_term +
        breakdown.dividends_qualified +
        breakdown.dividends_ordinary +
        breakdown.interest +
        breakdown.self_employment +
        breakdown.rental
    );
}

/**
 * Check if income breakdown has any non-zero values.
 * @param {object} breakdown - Income breakdown object
 * @returns {boolean} True if any income is specified
 */
function hasIncomeBreakdown(breakdown) {
    return calculateTotalIncome(breakdown) > 0;
}

// =============================================================================
// International Tax Calculation
// =============================================================================

function gatherIntlFormData() {
    const taxYear = parseInt(document.getElementById('intl-tax-year').value, 10);
    const countryCode = document.getElementById('intl-country').value;
    const incomeBreakdown = gatherIncomeBreakdown('intl');
    const totalIncome = calculateTotalIncome(incomeBreakdown);

    return {
        country_code: countryCode,
        tax_year: taxYear,
        gross_income: totalIncome,
        income: incomeBreakdown,
        currency_code: COUNTRY_CURRENCIES[countryCode] || 'USD'
    };
}

async function calculateInternationalTaxes() {
    // Validate form
    if (!intlForm.checkValidity()) {
        intlForm.reportValidity();
        return;
    }

    const formData = gatherIntlFormData();

    // Validate income
    if (formData.gross_income <= 0) {
        showError({ error: { message: 'Please enter at least one income amount.' } });
        return;
    }

    // Show loading, hide results and error
    showLoading('intl-calculate-btn');
    hideAllResults();
    hideError();

    try {
        const response = await fetch(`${API_BASE}/international/estimate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch {
                errorData = { error: { message: `HTTP ${response.status}: ${response.statusText}` } };
            }
            showError(errorData);
            return;
        }

        const result = await response.json();
        displayIntlResults(result);
    } catch (err) {
        showError({
            error: {
                message: 'Network error. Please check your connection and try again.'
            }
        });
    } finally {
        hideLoading('intl-calculate-btn');
    }
}

// =============================================================================
// Comparison Calculation
// =============================================================================

function gatherCompareFormData() {
    const taxYear = parseInt(document.getElementById('compare-tax-year').value, 10);
    const baseCurrency = document.getElementById('compare-currency').value;
    const filingStatus = document.getElementById('compare-filing-status')?.value || 'single';
    const incomeBreakdown = gatherIncomeBreakdown('compare');
    const totalIncome = calculateTotalIncome(incomeBreakdown);

    // Get selected regions
    const regionCheckboxes = document.querySelectorAll('input[name="regions"]:checked');
    const regions = Array.from(regionCheckboxes).map(cb => cb.value);

    return {
        base_currency: baseCurrency,
        gross_income: totalIncome,
        income: incomeBreakdown,
        regions: regions,
        tax_year: taxYear,
        filing_status: filingStatus
    };
}

async function calculateComparison() {
    // Validate form
    if (!compareForm.checkValidity()) {
        compareForm.reportValidity();
        return;
    }

    const formData = gatherCompareFormData();

    // Check that at least 2 regions are selected
    if (formData.regions.length < 2) {
        showError({ error: { message: 'Please select at least 2 countries to compare.' } });
        return;
    }

    // Check that some income is entered
    if (formData.gross_income <= 0) {
        showError({ error: { message: 'Please enter at least one income amount.' } });
        return;
    }

    // Show loading, hide results and error
    showLoading('compare-calculate-btn');
    hideAllResults();
    hideError();

    try {
        // Use enhanced comparison endpoint that supports US states, cities, and international
        const response = await fetch(`${API_BASE}/comparison/compare`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch {
                errorData = { error: { message: `HTTP ${response.status}: ${response.statusText}` } };
            }
            showError(errorData);
            return;
        }

        const result = await response.json();
        displayCompareResults(result);
    } catch (err) {
        showError({
            error: {
                message: 'Network error. Please check your connection and try again.'
            }
        });
    } finally {
        hideLoading('compare-calculate-btn');
    }
}

// =============================================================================
// Display Functions
// =============================================================================

function displayResults(result) {
    const summary = result.summary;
    const isRefund = summary.balance_due < 0;

    const federal = result.federal;

    // Populate bracket breakdown
    const bracketTable = document.getElementById('bracket-table').querySelector('tbody');
    bracketTable.innerHTML = '';

    if (federal.bracket_breakdown && federal.bracket_breakdown.length > 0) {
        federal.bracket_breakdown.forEach(bracket => {
            const tr = document.createElement('tr');
            const maxStr = bracket.bracket_max
                ? formatCurrency(bracket.bracket_max)
                : 'and above';
            tr.innerHTML = `
                <td>${formatCurrency(bracket.bracket_min)} - ${maxStr}</td>
                <td>${formatPercent(bracket.rate)}</td>
                <td>${formatCurrency(bracket.income_in_bracket)}</td>
                <td>${formatCurrency(bracket.tax_in_bracket)}</td>
            `;
            bracketTable.appendChild(tr);
        });
    } else {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="4" class="no-state-tax">No bracket information available</td>';
        bracketTable.appendChild(tr);
    }

    // Populate state results
    const stateResultsDiv = document.getElementById('state-results');
    stateResultsDiv.innerHTML = '';

    if (result.states && result.states.length > 0) {
        result.states.forEach(state => {
            const stateDiv = document.createElement('div');
            stateDiv.className = 'state-result';

            const stateHtml = `
                <h4>${state.jurisdiction_name} State Tax</h4>
                <table class="state-table">
                    <tbody>
                        <tr><td>State Taxable Income</td><td>${formatCurrency(state.taxable_income)}</td></tr>
                        <tr><td>Tax Before Credits</td><td>${formatCurrency(state.tax_before_credits)}</td></tr>
                        <tr><td>Total State Tax</td><td>${formatCurrency(state.total_tax)}</td></tr>
                        <tr><td>State Withholding</td><td>${formatCurrency(state.withholding)}</td></tr>
                        <tr class="${state.balance_due_or_refund < 0 ? 'result-positive' : 'result-negative'}">
                            <td>${state.balance_due_or_refund < 0 ? 'State Refund' : 'State Amount Owed'}</td>
                            <td>${formatCurrency(Math.abs(state.balance_due_or_refund))}</td>
                        </tr>
                    </tbody>
                </table>
            `;
            stateDiv.innerHTML = stateHtml;
            stateResultsDiv.appendChild(stateDiv);
        });
    } else {
        stateResultsDiv.innerHTML = '<p class="no-state-tax">No state tax calculation available.</p>';
    }

    // Populate disclaimers
    const disclaimerList = document.getElementById('disclaimer-list');
    disclaimerList.innerHTML = '';

    if (result.disclaimers && result.disclaimers.length > 0) {
        result.disclaimers.forEach(disclaimer => {
            const li = document.createElement('li');
            li.textContent = disclaimer;
            disclaimerList.appendChild(li);
        });
    }

    // Populate detailed breakdown sections (Phase 1)
    updateSummaryCard(summary);
    populateFederalBreakdown(federal);
    populateFICABreakdown(result);
    populateStateBreakdown(result.states);
    populateNIITBreakdown(federal);

    // Show results
    showResults();
}

// =============================================================================
// International Display
// =============================================================================

function displayIntlResults(result) {
    // Set country name
    const countryNameEl = document.getElementById('intl-country-name');
    if (countryNameEl) {
        countryNameEl.textContent = result.country_name || COUNTRY_NAMES[result.country_code] || result.country_code;
    }

    // Currency for formatting
    const currency = result.currency_code || 'USD';

    // Populate summary table
    const summaryTable = document.getElementById('intl-summary-table').querySelector('tbody');
    summaryTable.innerHTML = '';

    const summaryRows = [
        ['Gross Income', formatIntlCurrency(result.gross_income, currency)],
        ['---', ''],
        ['Total Tax', formatIntlCurrency(result.total_tax, currency), 'row-total'],
        ['Net Income', formatIntlCurrency(result.net_income, currency), 'row-total'],
        ['---', ''],
        ['Effective Rate', formatPercent(result.effective_rate)],
    ];

    if (result.marginal_rate) {
        summaryRows.push(['Marginal Rate', formatPercent(result.marginal_rate)]);
    }

    summaryRows.forEach(row => {
        if (row[0] === '---') {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="2"><hr></td>';
            summaryTable.appendChild(tr);
        } else {
            const tr = document.createElement('tr');
            if (row[2]) {
                tr.className = row[2];
            }
            tr.innerHTML = `<td>${row[0]}</td><td>${row[1]}</td>`;
            summaryTable.appendChild(tr);
        }
    });

    // Populate income type breakdown if available
    const incomeTypeSection = document.getElementById('intl-income-type-breakdown');
    const incomeTypeTable = document.getElementById('intl-income-type-table')?.querySelector('tbody');

    if (incomeTypeSection && incomeTypeTable) {
        incomeTypeTable.innerHTML = '';

        if (result.income_type_results && result.income_type_results.length > 0) {
            incomeTypeSection.hidden = false;
            result.income_type_results.forEach(incomeType => {
                if (parseFloat(incomeType.gross_amount) > 0) {
                    const tr = document.createElement('tr');
                    const treatmentClass = incomeType.treatment === 'exempt' ? 'result-positive' : '';
                    tr.innerHTML = `
                        <td>${escapeHtml(incomeType.income_type_display)}</td>
                        <td>${formatIntlCurrency(incomeType.gross_amount, currency)}</td>
                        <td>${formatIntlCurrency(incomeType.tax_amount, currency)}</td>
                        <td>${formatPercent(incomeType.effective_rate)}</td>
                        <td class="${treatmentClass}">${escapeHtml(capitalizeFirst(incomeType.treatment))}</td>
                    `;
                    incomeTypeTable.appendChild(tr);
                }
            });
        } else {
            incomeTypeSection.hidden = true;
        }
    }

    // Populate disclaimers
    const disclaimerList = document.getElementById('intl-disclaimer-list');
    disclaimerList.innerHTML = '';

    if (result.disclaimers && result.disclaimers.length > 0) {
        result.disclaimers.forEach(disclaimer => {
            const li = document.createElement('li');
            li.textContent = disclaimer;
            disclaimerList.appendChild(li);
        });
    }

    // Populate detailed breakdown sections (Phase 3)
    populateIntlDetailedBreakdowns(result);

    // Show results
    if (intlResultsSection) {
        intlResultsSection.hidden = false;
        intlResultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// =============================================================================
// Comparison Display
// =============================================================================

function displayCompareResults(result) {
    // Store result for modal access (Phase 2)
    lastCompareResult = result;

    // Set info text
    const infoEl = document.getElementById('compare-info');
    if (infoEl) {
        const symbol = CURRENCY_SYMBOLS[result.base_currency] || result.base_currency;
        const totalIncome = result.total_gross_income || result.gross_income || 0;
        infoEl.innerHTML = `Comparing tax on <strong>${symbol}${formatNumber(totalIncome)}</strong> gross income (${result.base_currency})`;
    }

    // Populate comparison table
    const compareTable = document.getElementById('compare-table').querySelector('tbody');
    compareTable.innerHTML = '';

    // Handle both old format (countries) and new format (regions)
    const regions = result.regions || result.countries || [];

    if (regions.length > 0) {
        // Sort by net income descending
        const sortedResults = [...regions].sort((a, b) =>
            parseFloat(b.net_income_base) - parseFloat(a.net_income_base)
        );

        sortedResults.forEach((region, index) => {
            const tr = document.createElement('tr');

            // Get region name - try various sources
            const regionId = region.region_id || region.country_code;
            const regionName = region.region_name || REGION_NAMES[regionId] || regionId;

            // Format amounts in base currency
            const baseCurrency = result.base_currency;
            const totalTax = formatIntlCurrency(region.total_tax_base, baseCurrency);
            const netIncome = formatIntlCurrency(region.net_income_base, baseCurrency);
            const effectiveRate = formatPercent(region.effective_rate);

            // Highlight best option
            let rowClass = '';
            if (index === 0) {
                rowClass = 'result-positive';
            }

            tr.className = rowClass;
            tr.dataset.regionId = regionId; // Store region ID for click handler
            tr.innerHTML = `
                <td>${escapeHtml(regionName)}</td>
                <td>${totalTax}</td>
                <td>${netIncome}</td>
                <td>${effectiveRate}</td>
            `;

            // Add click handler to open modal (Phase 2)
            tr.addEventListener('click', () => {
                openBreakdownModal(regionId);
            });
            tr.style.cursor = 'pointer';
            tr.title = 'Click for detailed breakdown';

            compareTable.appendChild(tr);
        });

        // Find best options
        const lowestTax = sortedResults.reduce((best, curr) =>
            parseFloat(curr.total_tax_base) < parseFloat(best.total_tax_base) ? curr : best
        );
        const highestNet = sortedResults[0]; // Already sorted by net income

        const lowestTaxEl = document.getElementById('lowest-tax-country');
        const highestNetEl = document.getElementById('highest-net-country');

        if (lowestTaxEl) {
            const lowestTaxId = lowestTax.region_id || lowestTax.country_code;
            lowestTaxEl.textContent = lowestTax.region_name || REGION_NAMES[lowestTaxId] || lowestTaxId;
        }
        if (highestNetEl) {
            const highestNetId = highestNet.region_id || highestNet.country_code;
            highestNetEl.textContent = highestNet.region_name || REGION_NAMES[highestNetId] || highestNetId;
        }
    }

    // Populate disclaimers
    const disclaimerList = document.getElementById('compare-disclaimer-list');
    disclaimerList.innerHTML = '';

    if (result.disclaimers && result.disclaimers.length > 0) {
        result.disclaimers.forEach(disclaimer => {
            const li = document.createElement('li');
            li.textContent = disclaimer;
            disclaimerList.appendChild(li);
        });
    }

    // Show results
    if (compareResultsSection) {
        compareResultsSection.hidden = false;
        compareResultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function showError(errorData) {
    const errorMessage = document.getElementById('error-message');

    let message = 'An unexpected error occurred.';

    if (errorData.error && errorData.error.message) {
        message = errorData.error.message;
    } else if (errorData.detail) {
        // FastAPI validation errors
        if (Array.isArray(errorData.detail)) {
            message = errorData.detail.map(d => `${d.loc.join('.')}: ${d.msg}`).join('; ');
        } else if (typeof errorData.detail === 'string') {
            message = errorData.detail;
        }
    } else if (errorData.message) {
        message = errorData.message;
    }

    errorMessage.textContent = message;
    errorSection.hidden = false;
}

function hideError() {
    errorSection.hidden = true;
}

function showResults() {
    resultsSection.hidden = false;
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function hideResults() {
    resultsSection.hidden = true;
}

function showLoading(buttonId = 'calculate-btn') {
    loadingSection.hidden = false;
    const btn = document.getElementById(buttonId);
    if (btn) btn.disabled = true;
}

function hideLoading(buttonId = 'calculate-btn') {
    loadingSection.hidden = true;
    const btn = document.getElementById(buttonId);
    if (btn) btn.disabled = false;
}

// =============================================================================
// Formatting Functions
// =============================================================================

function formatCurrency(amount) {
    if (amount === null || amount === undefined) {
        return '$0.00';
    }
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

function formatPercent(rate) {
    if (rate === null || rate === undefined) {
        return '0.00%';
    }
    // API returns rates as decimals (e.g., 0.22 for 22%)
    return (parseFloat(rate) * 100).toFixed(2) + '%';
}

function formatIntlCurrency(amount, currencyCode) {
    if (amount === null || amount === undefined) {
        amount = 0;
    }

    // Map currency codes to locales
    const localeMap = {
        'USD': 'en-US',
        'GBP': 'en-GB',
        'EUR': 'de-DE',
        'SGD': 'en-SG',
        'HKD': 'zh-HK',
        'AED': 'ar-AE',
        'JPY': 'ja-JP',
        'AUD': 'en-AU',
        'CAD': 'en-CA'
    };

    const locale = localeMap[currencyCode] || 'en-US';

    try {
        return new Intl.NumberFormat(locale, {
            style: 'currency',
            currency: currencyCode,
            minimumFractionDigits: currencyCode === 'JPY' ? 0 : 2,
            maximumFractionDigits: currencyCode === 'JPY' ? 0 : 2
        }).format(amount);
    } catch (e) {
        // Fallback for unsupported currencies
        const symbol = CURRENCY_SYMBOLS[currencyCode] || currencyCode;
        return `${symbol}${formatNumber(amount)}`;
    }
}

function formatNumber(amount) {
    if (amount === null || amount === undefined) {
        return '0.00';
    }
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// =============================================================================
// Detailed Breakdown Functions (Phase 1: US Tax Screen)
// =============================================================================

/**
 * Update the summary card with key figures.
 * @param {object} summary - Summary object from API response
 */
function updateSummaryCard(summary) {
    const totalTaxEl = document.getElementById('total-tax-display');
    const effectiveRateEl = document.getElementById('effective-rate-display');
    const marginalRateEl = document.getElementById('marginal-rate-display');
    const netIncomeEl = document.getElementById('net-income-display');

    if (totalTaxEl) totalTaxEl.textContent = formatCurrency(summary.total_tax);
    if (effectiveRateEl) effectiveRateEl.textContent = formatPercent(summary.effective_rate);
    if (marginalRateEl) marginalRateEl.textContent = formatPercent(summary.marginal_rate);
    if (netIncomeEl) {
        const netIncome = summary.total_income - summary.total_tax;
        netIncomeEl.textContent = formatCurrency(netIncome);
    }

    const badgeEl = document.getElementById('tax-status-badge');
    if (badgeEl) {
        const isRefund = summary.balance_due < 0;
        badgeEl.textContent = isRefund ? 'Estimated Refund' : 'Amount Owed';
        badgeEl.className = 'summary-card-badge ' + (isRefund ? 'refund' : 'owed');
    }
}

/**
 * Populate the federal income tax breakdown section.
 * @param {object} federal - Federal calculation object from API response
 */
function populateFederalBreakdown(federal) {
    const amountEl = document.getElementById('federal-total-amount');
    const pctEl = document.getElementById('federal-effective-pct');
    const contentEl = document.getElementById('federal-breakdown-content');

    if (!contentEl) return;

    // Update header amounts
    if (amountEl) amountEl.textContent = formatCurrency(federal.total_tax || federal.tax_before_credits);
    if (pctEl) {
        const grossIncome = federal.gross_income || 0;
        const effectiveRate = grossIncome > 0 ? (federal.total_tax / grossIncome) : 0;
        pctEl.textContent = `(${formatPercent(effectiveRate)})`;
    }

    // Build content
    let html = '';

    // Taxable income calculation
    html += `
        <div class="breakdown-nested">
            <div class="breakdown-nested-title">Taxable Income Calculation</div>
            <div class="breakdown-component">
                <span class="breakdown-component-name">Gross Income</span>
                <span class="breakdown-component-amount">${formatCurrency(federal.gross_income)}</span>
            </div>
            <div class="breakdown-component">
                <span class="breakdown-component-name">Adjustments (above-the-line)</span>
                <span class="breakdown-component-amount">-${formatCurrency(federal.adjustments || 0)}</span>
            </div>
            <div class="breakdown-component">
                <span class="breakdown-component-name">Adjusted Gross Income (AGI)</span>
                <span class="breakdown-component-amount">${formatCurrency(federal.adjusted_gross_income)}</span>
            </div>
            <div class="breakdown-component">
                <span class="breakdown-component-name">${escapeHtml(federal.deduction_type || 'Standard')} Deduction</span>
                <span class="breakdown-component-amount">-${formatCurrency(federal.deduction_amount)}</span>
            </div>
            <div class="breakdown-component" style="font-weight: bold;">
                <span class="breakdown-component-name">Taxable Income</span>
                <span class="breakdown-component-amount">${formatCurrency(federal.taxable_income)}</span>
            </div>
        </div>
    `;

    // Bracket breakdown if available
    if (federal.bracket_breakdown && federal.bracket_breakdown.length > 0) {
        html += `
            <div class="breakdown-nested">
                <div class="breakdown-nested-title">Tax Bracket Breakdown</div>
                <table class="bracket-breakdown-table">
                    <thead>
                        <tr>
                            <th>Bracket</th>
                            <th>Rate</th>
                            <th>Income</th>
                            <th>Tax</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        federal.bracket_breakdown.forEach((bracket, i) => {
            const maxStr = bracket.bracket_max ? formatCurrency(bracket.bracket_max) : '...';
            const isCurrent = bracket.income_in_bracket > 0;
            html += `
                <tr class="${isCurrent ? 'current-bracket' : ''}">
                    <td>${formatCurrency(bracket.bracket_min)} - ${maxStr}</td>
                    <td>${formatPercent(bracket.rate)}</td>
                    <td>${formatCurrency(bracket.income_in_bracket)}</td>
                    <td>${formatCurrency(bracket.tax_in_bracket)}</td>
                </tr>
            `;
        });
        html += `
                    </tbody>
                    <tfoot>
                        <tr>
                            <td colspan="3">Total Ordinary Income Tax</td>
                            <td>${formatCurrency(federal.tax_before_credits)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;
    }

    // Credits
    const totalCredits = (federal.total_nonrefundable_credits || 0) + (federal.total_refundable_credits || 0);
    if (totalCredits > 0) {
        html += `
            <div class="breakdown-nested">
                <div class="breakdown-nested-title">Tax Credits</div>
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Nonrefundable Credits</span>
                    <span class="breakdown-component-amount">-${formatCurrency(federal.total_nonrefundable_credits)}</span>
                </div>
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Refundable Credits</span>
                    <span class="breakdown-component-amount">-${formatCurrency(federal.total_refundable_credits)}</span>
                </div>
            </div>
        `;
    }

    // Additional taxes
    const additionalTaxes = (federal.self_employment_tax || 0) + (federal.additional_medicare_tax || 0) + (federal.net_investment_income_tax || 0);
    if (additionalTaxes > 0) {
        html += `
            <div class="breakdown-nested">
                <div class="breakdown-nested-title">Additional Federal Taxes</div>
        `;
        if (federal.self_employment_tax > 0) {
            html += `
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Self-Employment Tax</span>
                    <span class="breakdown-component-amount">${formatCurrency(federal.self_employment_tax)}</span>
                    <span class="breakdown-component-rate">(15.3%)</span>
                </div>
            `;
        }
        if (federal.additional_medicare_tax > 0) {
            html += `
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Additional Medicare Tax</span>
                    <span class="breakdown-component-amount">${formatCurrency(federal.additional_medicare_tax)}</span>
                    <span class="breakdown-component-rate">(0.9%)</span>
                </div>
            `;
        }
        if (federal.net_investment_income_tax > 0) {
            html += `
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Net Investment Income Tax</span>
                    <span class="breakdown-component-amount">${formatCurrency(federal.net_investment_income_tax)}</span>
                    <span class="breakdown-component-rate">(3.8%)</span>
                </div>
            `;
        }
        html += '</div>';
    }

    // Total
    html += `
        <div class="breakdown-component" style="font-weight: bold; margin-top: 1rem; padding-top: 1rem; border-top: 2px solid var(--color-border);">
            <span class="breakdown-component-name">Total Federal Income Tax</span>
            <span class="breakdown-component-amount">${formatCurrency(federal.total_tax)}</span>
        </div>
    `;

    contentEl.innerHTML = html;
}

/**
 * Populate the FICA breakdown section.
 * @param {object} result - Full API response
 */
function populateFICABreakdown(result) {
    const sectionEl = document.getElementById('fica-breakdown-section');
    const amountEl = document.getElementById('fica-total-amount');
    const pctEl = document.getElementById('fica-effective-pct');
    const contentEl = document.getElementById('fica-breakdown-content');

    if (!contentEl || !sectionEl) return;

    // Calculate FICA from wages (estimated)
    // Get tax year from result or default to current year
    const taxYear = result.tax_year || 2025;
    const ssWageBase = SS_WAGE_BASE[taxYear] || SS_WAGE_BASE[2025];

    const wages = result.summary?.total_income || 0;
    const ssTaxableWages = Math.min(wages, ssWageBase);
    const ssTax = ssTaxableWages * 0.062;
    const medicareTax = wages * 0.0145;
    const totalFICA = ssTax + medicareTax;

    if (amountEl) amountEl.textContent = formatCurrency(totalFICA);
    if (pctEl && wages > 0) {
        const rate = totalFICA / wages;
        pctEl.textContent = `(${formatPercent(rate)})`;
    }

    const formattedWageBase = formatCurrency(ssWageBase);
    let html = `
        <div class="fica-detail">
            <span class="fica-detail-label">Social Security (6.2%)</span>
            <span class="fica-detail-value">${formatCurrency(ssTax)}</span>
            <span class="fica-detail-label">Taxable wages (up to ${formattedWageBase})</span>
            <span class="fica-detail-value">${formatCurrency(ssTaxableWages)}</span>
            <span class="fica-detail-label">Medicare (1.45%)</span>
            <span class="fica-detail-value">${formatCurrency(medicareTax)}</span>
            <span class="fica-detail-label">Taxable wages (no limit)</span>
            <span class="fica-detail-value">${formatCurrency(wages)}</span>
        </div>
        <div class="breakdown-note">
            Note: FICA taxes are typically withheld by your employer. Additional Medicare Tax (0.9%) applies on wages over $200,000 for single filers.
        </div>
    `;

    contentEl.innerHTML = html;
}

/**
 * Populate the state tax breakdown section.
 * @param {Array} states - State results array from API response
 */
function populateStateBreakdown(states) {
    const sectionEl = document.getElementById('state-breakdown-section');
    const nameSummaryEl = document.getElementById('state-name-summary');
    const amountEl = document.getElementById('state-total-amount');
    const pctEl = document.getElementById('state-effective-pct');
    const contentEl = document.getElementById('state-breakdown-content');

    if (!sectionEl || !contentEl) return;

    if (!states || states.length === 0) {
        sectionEl.hidden = true;
        return;
    }

    sectionEl.hidden = false;
    const state = states[0]; // Primary state

    if (nameSummaryEl) nameSummaryEl.textContent = escapeHtml(state.jurisdiction_name || 'State');
    if (amountEl) amountEl.textContent = formatCurrency(state.total_tax);
    if (pctEl && state.taxable_income > 0) {
        const rate = state.total_tax / state.taxable_income;
        pctEl.textContent = `(${formatPercent(rate)})`;
    }

    let html = '';

    if (state.total_tax === 0) {
        html = `
            <div class="not-applicable">
                ${escapeHtml(state.jurisdiction_name)} has no state income tax.
            </div>
        `;
    } else {
        html = `
            <div class="breakdown-component">
                <span class="breakdown-component-name">State Taxable Income</span>
                <span class="breakdown-component-amount">${formatCurrency(state.taxable_income)}</span>
            </div>
            <div class="breakdown-component">
                <span class="breakdown-component-name">Tax Before Credits</span>
                <span class="breakdown-component-amount">${formatCurrency(state.tax_before_credits)}</span>
            </div>
        `;

        if (state.total_credits && state.total_credits > 0) {
            html += `
                <div class="breakdown-component">
                    <span class="breakdown-component-name">State Credits</span>
                    <span class="breakdown-component-amount">-${formatCurrency(state.total_credits)}</span>
                </div>
            `;
        }

        html += `
            <div class="breakdown-component" style="font-weight: bold;">
                <span class="breakdown-component-name">Total State Tax</span>
                <span class="breakdown-component-amount">${formatCurrency(state.total_tax)}</span>
            </div>
            <div class="breakdown-note">
                State tax rates vary significantly. Some states have flat rates, others have progressive brackets.
            </div>
        `;
    }

    contentEl.innerHTML = html;
}

/**
 * Populate the NIIT breakdown section if applicable.
 * @param {object} federal - Federal calculation object from API response
 */
function populateNIITBreakdown(federal) {
    const sectionEl = document.getElementById('niit-breakdown-section');
    const amountEl = document.getElementById('niit-total-amount');
    const contentEl = document.getElementById('niit-breakdown-content');

    if (!sectionEl || !contentEl) return;

    const niitAmount = federal.net_investment_income_tax || 0;

    if (niitAmount <= 0) {
        sectionEl.hidden = true;
        return;
    }

    sectionEl.hidden = false;
    if (amountEl) amountEl.textContent = formatCurrency(niitAmount);

    const html = `
        <div class="breakdown-component">
            <span class="breakdown-component-name">Net Investment Income</span>
            <span class="breakdown-component-amount">(Investment income subject to NIIT)</span>
        </div>
        <div class="breakdown-component">
            <span class="breakdown-component-name">NIIT Rate</span>
            <span class="breakdown-component-amount">3.8%</span>
        </div>
        <div class="breakdown-component" style="font-weight: bold;">
            <span class="breakdown-component-name">NIIT Amount</span>
            <span class="breakdown-component-amount">${formatCurrency(niitAmount)}</span>
        </div>
        <div class="breakdown-note">
            The Net Investment Income Tax applies to investment income when your Modified AGI exceeds $200,000 (single) or $250,000 (MFJ).
        </div>
    `;

    contentEl.innerHTML = html;
}

// =============================================================================
// Phase 2: Compare Screen Breakdown Modal
// =============================================================================

// Store comparison results for modal access
let lastCompareResult = null;

// Store the element that opened the modal for focus management
let lastFocusedElement = null;

/**
 * Setup the breakdown modal event listeners.
 */
function setupBreakdownModal() {
    const modal = document.getElementById('breakdown-modal');
    const closeBtn = document.getElementById('modal-close-btn');

    if (!modal) return;

    // Close on X button click
    if (closeBtn) {
        closeBtn.addEventListener('click', closeBreakdownModal);
    }

    // Close on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeBreakdownModal();
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeBreakdownModal();
        }
    });
}

/**
 * Open the breakdown modal for a specific region.
 * @param {string} regionId - The region ID to show breakdown for
 */
function openBreakdownModal(regionId) {
    const modal = document.getElementById('breakdown-modal');
    const regionNameEl = document.getElementById('modal-region-name');
    const totalTaxEl = document.getElementById('modal-total-tax');
    const bodyEl = document.getElementById('modal-body');
    const loadingEl = document.getElementById('modal-loading');

    if (!modal || !lastCompareResult) return;

    // Save the currently focused element for restoration on close
    lastFocusedElement = document.activeElement;

    // Show loading state initially
    if (loadingEl) loadingEl.style.display = 'block';
    if (bodyEl) {
        // Clear previous content but keep loading indicator
        const existingContent = bodyEl.querySelectorAll(':not(#modal-loading)');
        existingContent.forEach(el => el.remove());
    }

    // Find the region in results
    const regions = lastCompareResult.regions || lastCompareResult.countries || [];
    const region = regions.find(r => (r.region_id || r.country_code) === regionId);

    if (!region) {
        console.warn('Region not found:', regionId);
        if (loadingEl) loadingEl.style.display = 'none';
        if (bodyEl) bodyEl.innerHTML = '<p>Region data not found.</p>';
        return;
    }

    const baseCurrency = lastCompareResult.base_currency || 'USD';
    const regionName = region.region_name || REGION_NAMES[regionId] || regionId;

    if (regionNameEl) regionNameEl.textContent = escapeHtml(regionName);
    if (totalTaxEl) totalTaxEl.textContent = formatIntlCurrency(region.total_tax_base, baseCurrency);

    // Build modal content based on region type
    let html = '';

    if (region.region_type === 'us_state' || region.region_type === 'us_city') {
        html = buildUSBreakdownModalContent(region, baseCurrency);
    } else {
        html = buildInternationalBreakdownModalContent(region, baseCurrency);
    }

    // Hide loading and show content
    if (loadingEl) loadingEl.style.display = 'none';
    if (bodyEl) bodyEl.innerHTML = html;

    // Show modal
    modal.classList.add('active');
    document.body.style.overflow = 'hidden'; // Prevent background scroll

    // Move focus to the close button for accessibility
    const closeBtn = document.getElementById('modal-close-btn');
    if (closeBtn) {
        closeBtn.focus();
    }

    // Set up focus trap
    setupFocusTrap(modal);
}

/**
 * Close the breakdown modal.
 */
function closeBreakdownModal() {
    const modal = document.getElementById('breakdown-modal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = ''; // Restore scroll

        // Remove focus trap
        removeFocusTrap();

        // Restore focus to the element that opened the modal
        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        }
        lastFocusedElement = null;
    }
}

/**
 * Set up focus trap within the modal.
 * @param {HTMLElement} modal - The modal element
 */
function setupFocusTrap(modal) {
    if (!modal) return;

    // Get all focusable elements within the modal
    const focusableElements = modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    if (focusableElements.length === 0) return;

    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];

    // Store handler for removal
    modal._focusTrapHandler = function(e) {
        if (e.key !== 'Tab') return;

        if (e.shiftKey) {
            // Shift + Tab
            if (document.activeElement === firstFocusable) {
                e.preventDefault();
                lastFocusable.focus();
            }
        } else {
            // Tab
            if (document.activeElement === lastFocusable) {
                e.preventDefault();
                firstFocusable.focus();
            }
        }
    };

    modal.addEventListener('keydown', modal._focusTrapHandler);
}

/**
 * Remove focus trap from the modal.
 */
function removeFocusTrap() {
    const modal = document.getElementById('breakdown-modal');
    if (modal && modal._focusTrapHandler) {
        modal.removeEventListener('keydown', modal._focusTrapHandler);
        delete modal._focusTrapHandler;
    }
}

/**
 * Build modal content for US regions.
 * @param {object} region - Region result object
 * @param {string} baseCurrency - Base currency for formatting
 * @returns {string} HTML content
 */
function buildUSBreakdownModalContent(region, baseCurrency) {
    const bd = region.us_breakdown;
    if (!bd) {
        return '<p>No detailed breakdown available.</p>';
    }

    let html = '';

    // Summary section
    html += `
        <details class="breakdown-section" open>
            <summary>
                <span>Tax Summary</span>
                <span class="breakdown-section-amount">${formatCurrency(region.total_tax_local)}</span>
            </summary>
            <div class="breakdown-section-content">
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Gross Income</span>
                    <span class="breakdown-component-amount">${formatCurrency(region.gross_income_local)}</span>
                </div>
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Federal Taxable Income</span>
                    <span class="breakdown-component-amount">${formatCurrency(bd.federal_taxable_income)}</span>
                </div>
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Effective Rate</span>
                    <span class="breakdown-component-amount">${formatPercent(region.effective_rate)}</span>
                </div>
            </div>
        </details>
    `;

    // Federal breakdown
    html += `
        <details class="breakdown-section" open>
            <summary>
                <span>Federal Income Tax</span>
                <span class="breakdown-section-amount">${formatCurrency(bd.federal_tax)}</span>
            </summary>
            <div class="breakdown-section-content">
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Ordinary Income Tax</span>
                    <span class="breakdown-component-amount">${formatCurrency(bd.federal_ordinary_tax)}</span>
                </div>
    `;

    if (bd.federal_ltcg_tax > 0) {
        html += `
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Long-Term Capital Gains Tax</span>
                    <span class="breakdown-component-amount">${formatCurrency(bd.federal_ltcg_tax)}</span>
                </div>
        `;
        // LTCG bracket breakdown
        if (bd.ltcg_at_zero_percent > 0 || bd.ltcg_at_fifteen_percent > 0 || bd.ltcg_at_twenty_percent > 0) {
            html += `
                <div class="breakdown-nested">
                    <div class="breakdown-nested-title">LTCG/Qualified Dividend Brackets</div>
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">At 0%</span>
                        <span class="breakdown-component-amount">${formatCurrency(bd.ltcg_at_zero_percent)}</span>
                    </div>
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">At 15%</span>
                        <span class="breakdown-component-amount">${formatCurrency(bd.ltcg_at_fifteen_percent)}</span>
                    </div>
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">At 20%</span>
                        <span class="breakdown-component-amount">${formatCurrency(bd.ltcg_at_twenty_percent)}</span>
                    </div>
                </div>
            `;
        }
    }

    if (bd.federal_niit > 0) {
        html += `
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Net Investment Income Tax</span>
                    <span class="breakdown-component-amount">${formatCurrency(bd.federal_niit)}</span>
                    <span class="breakdown-component-rate">(3.8%)</span>
                </div>
        `;
    }

    html += `
                <div class="breakdown-component" style="font-weight: bold; border-top: 1px solid var(--color-border); padding-top: 0.5rem; margin-top: 0.5rem;">
                    <span class="breakdown-component-name">Total Federal Tax</span>
                    <span class="breakdown-component-amount">${formatCurrency(bd.federal_tax)}</span>
                    <span class="breakdown-component-rate">${formatPercent(bd.federal_effective_rate)}</span>
                </div>
            </div>
        </details>
    `;

    // State breakdown
    html += `
        <details class="breakdown-section">
            <summary>
                <span>State Tax (${escapeHtml(bd.state_name)})</span>
                <span class="breakdown-section-amount">${formatCurrency(bd.state_tax)}</span>
            </summary>
            <div class="breakdown-section-content">
    `;

    if (!bd.has_state_income_tax) {
        html += `
                <div class="not-applicable">
                    ${escapeHtml(bd.state_name)} has no state income tax.
                </div>
        `;
    } else {
        html += `
                <div class="breakdown-component">
                    <span class="breakdown-component-name">State Tax</span>
                    <span class="breakdown-component-amount">${formatCurrency(bd.state_tax)}</span>
                    <span class="breakdown-component-rate">${formatPercent(bd.state_effective_rate)}</span>
                </div>
        `;
    }

    html += `
            </div>
        </details>
    `;

    // Local breakdown (if applicable)
    if (bd.local_tax > 0 || bd.local_name) {
        html += `
            <details class="breakdown-section">
                <summary>
                    <span>Local Tax (${escapeHtml(bd.local_name || 'City')})</span>
                    <span class="breakdown-section-amount">${formatCurrency(bd.local_tax)}</span>
                </summary>
                <div class="breakdown-section-content">
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">Local Income Tax</span>
                        <span class="breakdown-component-amount">${formatCurrency(bd.local_tax)}</span>
                        <span class="breakdown-component-rate">${formatPercent(bd.local_effective_rate)}</span>
                    </div>
                </div>
            </details>
        `;
    }

    // Income type breakdown
    if (region.income_type_results && region.income_type_results.length > 0) {
        html += buildIncomeTypeBreakdownSection(region.income_type_results, 'USD');
    }

    return html;
}

/**
 * Build modal content for international regions.
 * @param {object} region - Region result object
 * @param {string} baseCurrency - Base currency for formatting
 * @returns {string} HTML content
 */
function buildInternationalBreakdownModalContent(region, baseCurrency) {
    const bd = region.international_breakdown;
    const localCurrency = region.currency_code || baseCurrency;

    let html = '';

    // Summary section
    html += `
        <details class="breakdown-section" open>
            <summary>
                <span>Tax Summary</span>
                <span class="breakdown-section-amount">${formatIntlCurrency(region.total_tax_local, localCurrency)}</span>
            </summary>
            <div class="breakdown-section-content">
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Gross Income (${localCurrency})</span>
                    <span class="breakdown-component-amount">${formatIntlCurrency(region.gross_income_local, localCurrency)}</span>
                </div>
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Total Tax (${localCurrency})</span>
                    <span class="breakdown-component-amount">${formatIntlCurrency(region.total_tax_local, localCurrency)}</span>
                </div>
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Net Income (${localCurrency})</span>
                    <span class="breakdown-component-amount">${formatIntlCurrency(region.net_income_local, localCurrency)}</span>
                </div>
                <div class="breakdown-component">
                    <span class="breakdown-component-name">Effective Rate</span>
                    <span class="breakdown-component-amount">${formatPercent(region.effective_rate)}</span>
                </div>
            </div>
        </details>
    `;

    // Component breakdown
    if (bd) {
        html += `
            <details class="breakdown-section" open>
                <summary>
                    <span>Tax Components</span>
                </summary>
                <div class="breakdown-section-content">
        `;

        // Income Tax
        html += `
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">${getIncomeTaxLabel(region.region_id)}</span>
                        <span class="breakdown-component-amount">${formatIntlCurrency(bd.income_tax, localCurrency)}</span>
                    </div>
        `;

        // Social Insurance
        if (bd.social_insurance > 0) {
            html += `
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">${getSocialInsuranceLabel(region.region_id)}</span>
                        <span class="breakdown-component-amount">${formatIntlCurrency(bd.social_insurance, localCurrency)}</span>
                    </div>
            `;
        }

        // Other Taxes
        if (bd.other_taxes > 0) {
            html += `
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">Other Taxes</span>
                        <span class="breakdown-component-amount">${formatIntlCurrency(bd.other_taxes, localCurrency)}</span>
                    </div>
            `;
        }

        html += `
                </div>
            </details>
        `;
    }

    // Income type breakdown
    if (region.income_type_results && region.income_type_results.length > 0) {
        html += buildIncomeTypeBreakdownSection(region.income_type_results, localCurrency);
    }

    // Notes
    if (region.notes && region.notes.length > 0) {
        html += `
            <div class="breakdown-note">
                ${escapeHtml(region.notes.join(' '))}
            </div>
        `;
    }

    return html;
}

/**
 * Build the income type breakdown section.
 * @param {Array} incomeTypes - Income type results array
 * @param {string} currency - Currency for formatting
 * @returns {string} HTML content
 */
function buildIncomeTypeBreakdownSection(incomeTypes, currency) {
    if (!incomeTypes || incomeTypes.length === 0) return '';

    let html = `
        <details class="breakdown-section">
            <summary>
                <span>Tax by Income Type</span>
            </summary>
            <div class="breakdown-section-content">
                <table class="income-type-table">
                    <thead>
                        <tr>
                            <th>Income Type</th>
                            <th>Gross</th>
                            <th>Tax</th>
                            <th>Rate</th>
                            <th>Treatment</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    incomeTypes.forEach(it => {
        if (parseFloat(it.gross_amount) > 0) {
            const treatmentClass = it.treatment === 'exempt' ? 'exempt' : (it.treatment === 'preferential' ? 'preferential' : '');
            html += `
                <tr>
                    <td>${escapeHtml(it.income_type_display)}</td>
                    <td>${formatIntlCurrency(it.gross_amount, currency)}</td>
                    <td>${formatIntlCurrency(it.tax_amount, currency)}</td>
                    <td>${formatPercent(it.effective_rate)}</td>
                    <td class="${treatmentClass}">${escapeHtml(capitalizeFirst(it.treatment))}</td>
                </tr>
            `;
        }
    });

    html += `
                    </tbody>
                </table>
            </div>
        </details>
    `;

    return html;
}

/**
 * Get country-specific income tax label.
 * @param {string} regionId - Region/country code
 * @returns {string} Label
 */
function getIncomeTaxLabel(regionId) {
    const labels = {
        'GB': 'Income Tax',
        'DE': 'Einkommensteuer',
        'FR': 'Impot sur le revenu',
        'JP': 'Income Tax + Resident Tax',
        'AU': 'Income Tax + Medicare Levy',
        'SG': 'Income Tax',
        'HK': 'Salaries Tax',
        'AE': 'Income Tax',
    };
    return labels[regionId] || 'Income Tax';
}

/**
 * Get country-specific social insurance label.
 * @param {string} regionId - Region/country code
 * @returns {string} Label
 */
function getSocialInsuranceLabel(regionId) {
    const labels = {
        'GB': 'National Insurance',
        'DE': 'Social Insurance',
        'FR': 'CSG/CRDS + Social Charges',
        'JP': 'Social Insurance',
        'AU': 'N/A',
        'SG': 'CPF (Employee)',
        'HK': 'MPF (Employee)',
        'AE': 'N/A',
    };
    return labels[regionId] || 'Social Insurance';
}

// =============================================================================
// Phase 3: International Tax Screen Breakdowns
// =============================================================================

/**
 * Populate the international detailed breakdown sections.
 * @param {object} result - International tax result from API
 */
function populateIntlDetailedBreakdowns(result) {
    const currency = result.currency_code || 'USD';
    const grossIncome = result.gross_income || 0;

    // Update summary card
    updateIntlSummaryCard(result);

    // Income Tax section
    populateIntlIncomeTaxSection(result, currency, grossIncome);

    // Social Insurance section
    populateIntlSocialInsuranceSection(result, currency, grossIncome);

    // Other Taxes section
    populateIntlOtherTaxesSection(result, currency, grossIncome);

    // Income Type section
    populateIntlIncomeTypeSection(result, currency);
}

/**
 * Update the international summary card.
 * @param {object} result - International tax result
 */
function updateIntlSummaryCard(result) {
    const currency = result.currency_code || 'USD';

    const totalTaxEl = document.getElementById('intl-total-tax-display');
    const taxLabelEl = document.getElementById('intl-tax-label');
    const effectiveRateEl = document.getElementById('intl-effective-rate-display');
    const marginalRateEl = document.getElementById('intl-marginal-rate-display');
    const netIncomeEl = document.getElementById('intl-net-income-display');

    if (totalTaxEl) totalTaxEl.textContent = formatIntlCurrency(result.total_tax, currency);
    if (taxLabelEl) taxLabelEl.textContent = `Total Tax Liability (${currency})`;
    if (effectiveRateEl) effectiveRateEl.textContent = formatPercent(result.effective_rate);
    if (marginalRateEl) {
        if (result.marginal_rate) {
            marginalRateEl.textContent = formatPercent(result.marginal_rate);
        } else {
            marginalRateEl.textContent = '--';
        }
    }
    if (netIncomeEl) netIncomeEl.textContent = formatIntlCurrency(result.net_income, currency);
}

/**
 * Populate the income tax breakdown section for international.
 * @param {object} result - International tax result
 * @param {string} currency - Currency code
 * @param {number} grossIncome - Gross income
 */
function populateIntlIncomeTaxSection(result, currency, grossIncome) {
    const sectionEl = document.getElementById('intl-income-tax-section');
    const amountEl = document.getElementById('intl-income-tax-amount');
    const pctEl = document.getElementById('intl-income-tax-pct');
    const contentEl = document.getElementById('intl-income-tax-content');

    if (!sectionEl || !contentEl) return;

    const incomeTax = result.income_tax || 0;

    if (amountEl) amountEl.textContent = formatIntlCurrency(incomeTax, currency);
    if (pctEl && grossIncome > 0) {
        const rate = incomeTax / grossIncome;
        pctEl.textContent = `(${formatPercent(rate)})`;
    }

    let html = '';

    if (incomeTax === 0 && result.country_code === 'AE') {
        html = '<div class="not-applicable">UAE has no personal income tax.</div>';
    } else if (result.breakdown && result.breakdown.length > 0) {
        // Show bracket breakdown from API if available
        html = '<div class="breakdown-nested"><div class="breakdown-nested-title">Income Tax Brackets</div>';
        result.breakdown.forEach(component => {
            if (component.component_id && component.component_id.includes('BRACKET')) {
                html += `
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">${escapeHtml(component.name)}</span>
                        <span class="breakdown-component-amount">${formatIntlCurrency(component.amount, currency)}</span>
                    </div>
                `;
            }
        });
        html += '</div>';
    } else {
        html = `
            <div class="breakdown-component">
                <span class="breakdown-component-name">Taxable Income</span>
                <span class="breakdown-component-amount">${formatIntlCurrency(result.taxable_income, currency)}</span>
            </div>
            <div class="breakdown-component" style="font-weight: bold;">
                <span class="breakdown-component-name">Income Tax</span>
                <span class="breakdown-component-amount">${formatIntlCurrency(incomeTax, currency)}</span>
            </div>
        `;
    }

    contentEl.innerHTML = html;
}

/**
 * Populate the social insurance breakdown section for international.
 * @param {object} result - International tax result
 * @param {string} currency - Currency code
 * @param {number} grossIncome - Gross income
 */
function populateIntlSocialInsuranceSection(result, currency, grossIncome) {
    const sectionEl = document.getElementById('intl-social-insurance-section');
    const labelEl = document.getElementById('intl-social-insurance-label');
    const amountEl = document.getElementById('intl-social-insurance-amount');
    const pctEl = document.getElementById('intl-social-insurance-pct');
    const contentEl = document.getElementById('intl-social-insurance-content');

    if (!sectionEl || !contentEl) return;

    const socialInsurance = result.social_insurance || 0;

    // Update label based on country
    if (labelEl) labelEl.textContent = getSocialInsuranceLabel(result.country_code);

    if (amountEl) amountEl.textContent = formatIntlCurrency(socialInsurance, currency);
    if (pctEl && grossIncome > 0) {
        const rate = socialInsurance / grossIncome;
        pctEl.textContent = `(${formatPercent(rate)})`;
    }

    let html = '';

    if (socialInsurance === 0) {
        if (result.country_code === 'AE') {
            html = '<div class="not-applicable">UAE has no social insurance contributions for employees.</div>';
        } else {
            html = '<div class="not-applicable">No social insurance calculated for this income level.</div>';
        }
    } else {
        // Show breakdown from API if available
        const siComponents = (result.breakdown || []).filter(c =>
            c.component_id && (c.component_id.includes('NI') || c.component_id.includes('SOCIAL') || c.component_id.includes('CPF'))
        );

        if (siComponents.length > 0) {
            siComponents.forEach(component => {
                html += `
                    <div class="breakdown-component">
                        <span class="breakdown-component-name">${escapeHtml(component.name)}</span>
                        <span class="breakdown-component-amount">${formatIntlCurrency(component.amount, currency)}</span>
                    </div>
                `;
            });
        } else {
            html = `
                <div class="breakdown-component" style="font-weight: bold;">
                    <span class="breakdown-component-name">${getSocialInsuranceLabel(result.country_code)}</span>
                    <span class="breakdown-component-amount">${formatIntlCurrency(socialInsurance, currency)}</span>
                </div>
            `;
        }
    }

    contentEl.innerHTML = html;
}

/**
 * Populate the other taxes breakdown section for international.
 * @param {object} result - International tax result
 * @param {string} currency - Currency code
 * @param {number} grossIncome - Gross income
 */
function populateIntlOtherTaxesSection(result, currency, grossIncome) {
    const sectionEl = document.getElementById('intl-other-taxes-section');
    const amountEl = document.getElementById('intl-other-taxes-amount');
    const pctEl = document.getElementById('intl-other-taxes-pct');
    const contentEl = document.getElementById('intl-other-taxes-content');

    if (!sectionEl || !contentEl) return;

    const otherTaxes = result.other_taxes || 0;

    if (otherTaxes <= 0) {
        sectionEl.hidden = true;
        return;
    }

    sectionEl.hidden = false;

    if (amountEl) amountEl.textContent = formatIntlCurrency(otherTaxes, currency);
    if (pctEl && grossIncome > 0) {
        const rate = otherTaxes / grossIncome;
        pctEl.textContent = `(${formatPercent(rate)})`;
    }

    // Show breakdown from API if available
    const otherComponents = (result.breakdown || []).filter(c =>
        c.component_id && !c.component_id.includes('BRACKET') && !c.component_id.includes('NI') && !c.component_id.includes('SOCIAL')
    );

    let html = '';
    if (otherComponents.length > 0) {
        otherComponents.forEach(component => {
            html += `
                <div class="breakdown-component">
                    <span class="breakdown-component-name">${escapeHtml(component.name)}</span>
                    <span class="breakdown-component-amount">${formatIntlCurrency(component.amount, currency)}</span>
                </div>
            `;
        });
    } else {
        html = `
            <div class="breakdown-component">
                <span class="breakdown-component-name">Other Taxes</span>
                <span class="breakdown-component-amount">${formatIntlCurrency(otherTaxes, currency)}</span>
            </div>
        `;
    }

    contentEl.innerHTML = html;
}

/**
 * Populate the income type breakdown section for international.
 * @param {object} result - International tax result
 * @param {string} currency - Currency code
 */
function populateIntlIncomeTypeSection(result, currency) {
    const sectionEl = document.getElementById('intl-income-type-section');
    const contentEl = document.getElementById('intl-income-type-content');

    if (!sectionEl || !contentEl) return;

    if (!result.income_type_results || result.income_type_results.length === 0) {
        sectionEl.hidden = true;
        return;
    }

    sectionEl.hidden = false;

    let html = `
        <table class="income-type-table">
            <thead>
                <tr>
                    <th>Income Type</th>
                    <th>Gross</th>
                    <th>Tax</th>
                    <th>Rate</th>
                    <th>Treatment</th>
                </tr>
            </thead>
            <tbody>
    `;

    result.income_type_results.forEach(it => {
        if (parseFloat(it.gross_amount) > 0) {
            const treatmentClass = it.treatment === 'exempt' ? 'exempt' : (it.treatment === 'preferential' ? 'preferential' : '');
            html += `
                <tr>
                    <td>${escapeHtml(it.income_type_display)}</td>
                    <td>${formatIntlCurrency(it.gross_amount, currency)}</td>
                    <td>${formatIntlCurrency(it.tax_amount, currency)}</td>
                    <td>${formatPercent(it.effective_rate)}</td>
                    <td class="${treatmentClass}">${escapeHtml(capitalizeFirst(it.treatment))}</td>
                </tr>
            `;
        }
    });

    html += '</tbody></table>';

    contentEl.innerHTML = html;
}

// =============================================================================
// Initialize modal on DOMContentLoaded
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    setupBreakdownModal();
    setupDetailsAriaExpanded();
});

/**
 * Setup aria-expanded state management for all details elements.
 * This improves accessibility for screen readers and older assistive technologies.
 */
function setupDetailsAriaExpanded() {
    const detailsElements = document.querySelectorAll('details');

    detailsElements.forEach(details => {
        // Set initial aria-expanded state based on open attribute
        details.setAttribute('aria-expanded', details.open ? 'true' : 'false');

        // Listen for toggle events to update aria-expanded
        details.addEventListener('toggle', () => {
            details.setAttribute('aria-expanded', details.open ? 'true' : 'false');
        });
    });
}
