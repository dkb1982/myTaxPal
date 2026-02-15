"""
ZIP code to jurisdiction lookup.

Maps ZIP codes to local tax jurisdictions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ZipLookupError(Exception):
    """Exception raised during ZIP lookup."""

    pass


class ZipJurisdictionLookup:
    """
    Lookup for mapping ZIP codes to local tax jurisdictions.

    IMPORTANT: ZIP mappings are PLACEHOLDER data and may not be accurate.
    """

    def __init__(self, mapping_file: Path | None = None):
        """
        Initialize the lookup.

        Args:
            mapping_file: Path to ZIP mapping YAML file.
                         Defaults to project rules/zip_jurisdictions.yaml
        """
        if mapping_file is None:
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent.parent
            mapping_file = project_root / "rules" / "zip_jurisdictions.yaml"

        self.mapping_file = mapping_file
        self._zip_mappings: dict[str, str] = {}
        self._state_mappings: dict[str, str] = {}
        self._loaded = False

    def _load_mappings(self) -> None:
        """Load ZIP mappings from YAML file."""
        if self._loaded:
            return

        if not self.mapping_file.exists():
            raise ZipLookupError(f"ZIP mapping file not found: {self.mapping_file}")

        try:
            with open(self.mapping_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ZipLookupError(f"Failed to parse ZIP mappings: {e}") from e

        self._zip_mappings = data.get("zip_mappings", {})
        self._state_mappings = data.get("state_zip_prefixes", {})
        self._loaded = True

    def lookup_local_jurisdiction(self, zip_code: str) -> str | None:
        """
        Look up the local tax jurisdiction for a ZIP code.

        IMPORTANT LIMITATION: This lookup uses only the first 3 digits (ZIP prefix)
        of the ZIP code. This may result in:
        - Some ZIP codes within a 3-digit prefix being mapped to a jurisdiction
          they don't actually belong to
        - Multiple jurisdictions within the same 3-digit prefix area being
          collapsed to a single result

        For more accurate results, consider using a full 5-digit ZIP to
        jurisdiction database.

        Args:
            zip_code: 5-digit ZIP code or 3-digit prefix

        Returns:
            Jurisdiction ID (e.g., "US-NY-NYC") or None if not found
        """
        self._load_mappings()

        # Normalize ZIP code
        # NOTE: We only use the first 3 digits for lookup. This is a known
        # limitation - some jurisdictions (e.g., NYC) span multiple prefixes,
        # and some prefixes contain multiple jurisdictions.
        zip_code = zip_code.strip()
        if len(zip_code) >= 3:
            prefix = zip_code[:3]
        else:
            prefix = zip_code

        return self._zip_mappings.get(prefix)

    def lookup_state(self, zip_code: str) -> str | None:
        """
        Look up the state for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code or 3-digit prefix

        Returns:
            Two-letter state code or None if not found
        """
        self._load_mappings()

        # Normalize ZIP code
        zip_code = zip_code.strip()
        if len(zip_code) >= 3:
            prefix = zip_code[:3]
        else:
            prefix = zip_code

        return self._state_mappings.get(prefix)

    def lookup(self, zip_code: str) -> dict[str, str | None]:
        """
        Look up both state and local jurisdiction for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code or 3-digit prefix

        Returns:
            Dict with "state" and "local_jurisdiction" keys
        """
        return {
            "state": self.lookup_state(zip_code),
            "local_jurisdiction": self.lookup_local_jurisdiction(zip_code),
        }

    def get_all_local_jurisdictions(self) -> list[str]:
        """Get all local jurisdictions in the mapping."""
        self._load_mappings()
        return sorted(set(self._zip_mappings.values()))

    def get_zips_for_jurisdiction(self, jurisdiction_id: str) -> list[str]:
        """Get all ZIP prefixes for a jurisdiction."""
        self._load_mappings()
        return [
            zip_prefix for zip_prefix, jur_id in self._zip_mappings.items()
            if jur_id == jurisdiction_id
        ]

    def reload(self) -> None:
        """Force reload of mappings from file."""
        self._loaded = False
        self._zip_mappings = {}
        self._state_mappings = {}
        self._load_mappings()
