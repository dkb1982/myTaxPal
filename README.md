# Tax Estimator API

A stateless tax estimation API for calculating federal and state tax liabilities.

## Calculation repair status (September 2026)

The supported rules year is **2025** (UK: **2025/26**, 6 April 2025–5 April 2026).
Other years are rejected, not calculated using relabelled rules.

US single estimates and Compare now share the main calculation pipeline. UK
calculations preserve wages, self-employment, savings, dividends and capital gains.
The repairs include 2025 US deductions/credits, Social Security benefit taxability,
capital-loss netting, payroll and Additional Medicare; UK allowance/band/relief/NI
fixes; CA exemption credits; and state/local payment/result wiring.

`summary.total_tax` is federal/state/local liability (including SE and other federal
taxes). `summary.total_modelled_deductions` adds ordinary **employee** Social Security
and Medicare. `total_statutory_deductions` is retained as a compatibility alias,
not a promise of complete statutory coverage. The modelled amount is the
headline/Compare total; payroll is never added to the tax-return balance due.
`net_income` is before unmodelled state/local disability, paid-leave and unemployment
contributions, personal pension payments and living costs. Income-category tax
allocations are omitted where they are not authoritative.

### US state/city repair scope

The new 2025 state/city policies target a single, age-40, full-year resident working
in the same jurisdiction, without dependants, using standard/default deductions,
wages, corporate dividends and direct personal securities gains. The simple UI
and Compare disclose age 40. Standalone API callers supply `filer.age_at_year_end`
or a date of birth; missing age is not inferred. Other profiles remain explicitly
unvalidated. Source and boundary tests are separate from API/Compare parity tests.

`us_scenario` accepts optional monetary facts (USD for estimates; `base_currency`
for Compare):

- `az_post_2011_eligible_long_term_gains`: needed for Arizona positive LT gains.
- `philly_gains_held_six_months_or_less`: needed for Philadelphia positive ST gains.
- `philly_first_half_wages`: needed for Philadelphia wages, reflecting its July rate change.

Blank facts are unknown, not zero. A selected component that cannot be calculated
fails the estimate/whole comparison instead of publishing an incomplete ranking.
Eligibility-based credits still require their applicable legal facts. Refundable
state/local credits can make a component negative.

Standalone `income.dividends.ordinary` includes its `qualified` subset. Compare
`income.dividends_ordinary` is the **non-qualified** amount, added to the separate
`dividends_qualified` amount. The forms label this distinction.

Country profiles are available through the API. Compare accepts `country_profiles`
keyed by selected country codes; supply income through the common `income` breakdown,
not the profiles. Profile relief amounts are in destination currency. The UI exposes
UK region and Singapore citizen/PR status; results disclose other profile defaults.
FX uses published IRS **2025 annual averages**, not current market rates.

This is not comprehensive filing software or professional certification. US state
adjustments/credits/local coverage remain limited; multistate/part-year scenarios
are rejected. Eligibility-based federal credits require explicit facts/assertions.
UK mixed employment/self-employment NI and special NI categories are rejected.
Other international calculators remain unvalidated estimates. Cross-border/treaty
taxation, continued home-country obligations and cost-of-living comparisons are not
modelled. Regression cases and sources are in
`tests/test_calculation_repair_integration.py`, `tests/calculation/test_gb_repairs.py`
and the federal repair tests; passing tests does not establish full legal coverage.

**DISCLAIMER**: This application is for estimation purposes only and does not constitute tax advice. Consult a qualified tax professional for actual tax filing.

## Setup

### Prerequisites

- Python 3.11 or higher
- pip or uv package manager

### Installation

```bash
# Clone the repository
cd tax-estimator

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (including dev dependencies)
pip install -e ".[dev]"
```

### Running the API

```bash
# Development server with auto-reload
uvicorn tax_estimator.main:app --reload --port 8000

# Or using the script entry point
tax-estimator
```

The API will be available at http://localhost:8000

### API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tax_estimator --cov-report=term-missing

# Run specific test file
pytest tests/test_rules_loader.py -v
```

## Project Structure

```
tax-estimator/
├── pyproject.toml          # Modern Python packaging
├── README.md               # This file
├── src/
│   └── tax_estimator/
│       ├── __init__.py
│       ├── main.py         # FastAPI app entry point
│       ├── api/            # API routes
│       ├── calculation/    # Tax calculation engine
│       ├── models/         # Pydantic request/response models
│       ├── rules/          # Tax rules loading/validation
│       │   ├── loader.py   # YAML loader
│       │   └── schema.py   # Pydantic models for rules
│       └── config.py       # App configuration
├── rules/                  # YAML tax rule files
│   ├── federal/
│   │   └── 2025.yaml      # Federal tax rules
│   └── states/
│       └── (state rules)
└── tests/
    ├── conftest.py        # pytest fixtures
    └── fixtures/          # Test YAML files
```

## Tax Rules

Tax rules are stored as YAML files in the `rules/` directory. Each jurisdiction and tax year has its own file.

**IMPORTANT**: Source-checked US/UK repair scenarios are distinguished from remaining
placeholder or unvalidated rules. Verify applicability before relying on an estimate;
the application's source checks are not professional tax sign-off.

## License

MIT
