# Tax Estimator API

A stateless tax estimation API for calculating federal and state tax liabilities.

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

**IMPORTANT**: All tax values in the placeholder files are FAKE and for development/testing only. Do not use for actual tax calculations.

## License

MIT
