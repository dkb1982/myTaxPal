# myTaxPal (tax-estimator)

A stateless take-home pay estimator: FastAPI service plus a vanilla HTML/CSS/JS
frontend, with tax rules bundled as YAML. No database or accounts.

## Calculation repair status (October 2026)

The broad source-reviewed US state/city rules are for **2025** (UK: **2025/26**,
6 April 2025–5 April 2026). A limited **2026 US federal + eight no-individual-income-tax states** estimate is
also available. Other years and unsupported 2026 jurisdictions are rejected,
not calculated using relabelled rules.

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

The 2026 release supports AK, FL, NV, NH, SD, TN, TX and WY: single, age 40, no dependants,
full-year residence and employment in the selected state, standard deduction, wages, ordinary
and qualified dividends, and direct short- and long-term securities gains.
Federal 2026 brackets, deductions, preferential thresholds and payroll wage
base come from the 2026 rule file; these states impose no individual income tax.
The website and APIs show only these supported 2026 destinations. Washington is
not included because of its capital-gains excise. There is no 2026
international, city or FX comparison yet; qualified tips/overtime, car-loan
interest, charitable and other special deductions are not modelled. See
`tests/test_2026_public_api.py` and `tests/calculation/states/test_2026_zero_tax_states.py`
for independent numeric reference cases and
`rules/federal/2026.yaml` for the primary-source links.

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
2025 comparisons use published IRS **2025 annual averages**, not current market
rates. The 2026 US path is USD-only and applies no FX rate.

This is not comprehensive filing software or professional certification. US state
adjustments/credits/local coverage remain limited; multistate/part-year scenarios
are rejected. Eligibility-based federal credits require explicit facts/assertions.
UK mixed employment/self-employment NI and special NI categories are rejected.
Cross-border/treaty
taxation, continued home-country obligations and cost-of-living comparisons are not
modelled. Regression cases and sources are in
`tests/test_calculation_repair_integration.py`, `tests/calculation/test_gb_repairs.py`
and the federal repair tests; passing tests does not establish full legal coverage.

### International calculators (October 2026)

All twelve country calculators load parameters for the requested year from
`rules/countries/<cc>/<year>.yaml` (2025 and 2026). `tax_year` N means the native
tax year with most of its months in calendar N. Each has hand-calculated reference
tests in `tests/calculation/countries/` (working and source links in the test
comments) plus a Compare-path parity test.

2026 covers a single resident employee with no dependants: wages, interest,
dividends and capital gains. Married/family profiles, self-employment and rental
income are refused. France (2026 brackets from the PLF 2027, not yet enacted), Italy
(default surtax rates) and Canada/Alberta (one derived threshold) carry provisional
warnings. 2026 Compare converts currency at the IRS 2025 annual averages until the
2026 averages are published.

| Code | `tax_year` 2025 means (2026 is the next one) | Notes |
| --- | --- | --- |
| GB | 2025/26 | Income tax, NI, dividends, savings, CGT, Scottish bands |
| DE | Calendar 2025 | §32a tariff, Vorsorgeaufwendungen, Soli zone, 25% Abgeltungsteuer |
| FR | 2025 income | Employee contributions, décote, quotient familial, PFU |
| IT | 2025 | IRPEF 23/35/43, art. 13 credit, 2025 cuneo fiscale, 26% on capital |
| ES | 2025 | Madrid scale by default; savings base; foral regions rejected |
| PT | 2025 income | Lei 55-A/2025 brackets, 28% capital rate, legacy NHR at 20% |
| CA | 2025 | Credit-based; ON, BC, AB supported; QC and others rejected |
| AU | FY 2025-26 | LITO, Medicare shade-in, MLS (assumes no hospital cover), CGT discount, franking |
| JP | Calendar 2025 | 2025 deduction reform, resident tax, 20.315% separate taxation |
| SG | 2025 income (YA2026) | Earned income relief, no YA2026 rebate, 2025 CPF rates |
| HK | 2025/26 | Includes the enacted HK$3,000 one-off reduction |
| AE | 2025 | No personal income tax; GPSSA for nationals not modelled |

Income a calculator does not model (for example self-employment in DE/FR/IT/ES/PT,
Italian rental income, Quebec) is rejected with a clear error rather than taxed as
salary. These are estimates for a default profile per country, not filing advice.

**DISCLAIMER**: This application is for estimation purposes only and does not constitute tax advice. Consult a qualified tax professional for actual tax filing.

## Setup

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (dependencies are locked in `uv.lock`)
- Node.js, only for the frontend runtime check

### Running locally

```bash
cd tax-estimator
uv sync --extra dev
uv run uvicorn tax_estimator.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000. API docs (`/docs`, `/redoc`) are only served when
`TAX_ESTIMATOR_DEBUG=true`; see `.env.example` for all settings.

### Docker

```bash
docker build -t mytaxpal .
docker run --rm -p 8000:8000 mytaxpal
```

The image runs as a non-root user with a `/health` healthcheck. Rate limiting is
in-memory per process; put a platform/edge limiter in front for multiple replicas.

### Checks (also run in CI, `.github/workflows/ci.yml`)

```bash
uv run ruff check --select F src tests
uv run pytest -q -o addopts= --disable-warnings
node --check static/js/app.js && node tests/frontend_repair_runtime.cjs
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
│   │   ├── 2025.yaml      # Federal tax rules
│   │   └── 2026.yaml      # Limited current-year release
│   └── states/
│       ├── (flat 2025 state rules)
│       └── 2026/         # Eight verified zero-income-tax states
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
