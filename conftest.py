"""
Root conftest.py - runs before any test imports.

Sets up environment variables for test mode.
"""

import os

# Set test environment variables BEFORE any application imports
os.environ["TAX_ESTIMATOR_RATE_LIMIT_ENABLED"] = "false"
os.environ["TAX_ESTIMATOR_DEBUG"] = "true"
