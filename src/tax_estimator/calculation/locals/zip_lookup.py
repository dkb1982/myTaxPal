"""
ZIP code to jurisdiction lookup.

Maps ZIP codes to states.
"""

from __future__ import annotations

from pathlib import Path
import re

import yaml


ZIP_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")


class ZipLookupError(Exception):
    """Exception raised during ZIP lookup."""

    pass


class ZipJurisdictionLookup:
    """
    Lookup for mapping ZIP codes to states.

    ZIP prefixes are intentionally not used to infer a local tax jurisdiction:
    a ZIP can cover multiple cities, counties, and tax districts.  A caller must
    provide an explicit covered-city ID to calculate local tax.
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
        """Return no local jurisdiction; ZIP alone cannot confirm a city."""
        self._normalize_base_zip(zip_code)
        # Keep this compatibility method so existing callers receive an explicit
        # no-result rather than silently selecting a city from stale prefix data.
        return None

    @staticmethod
    def _normalize_base_zip(zip_code: str) -> str:
        """Validate a five-digit or ZIP+4 value and return its five-digit base."""
        normalized = zip_code.strip()
        if not ZIP_PATTERN.fullmatch(normalized):
            raise ZipLookupError("ZIP code must be five digits or ZIP+4 (12345-6789)")
        return normalized[:5]

    def lookup_state(self, zip_code: str) -> str | None:
        """
        Look up the state for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code or ZIP+4

        Returns:
            Two-letter state code or None if not found
        """
        self._load_mappings()

        prefix = self._normalize_base_zip(zip_code)[:3]

        return self._state_mappings.get(prefix)

    def lookup(self, zip_code: str) -> dict[str, str | None]:
        """
        Look up state and report that no local jurisdiction is confirmed.

        Args:
            zip_code: 5-digit ZIP code or ZIP+4

        Returns:
            Dict with "state" and "local_jurisdiction" keys
        """
        return {
            "state": self.lookup_state(zip_code),
            "local_jurisdiction": self.lookup_local_jurisdiction(zip_code),
        }

    def get_all_local_jurisdictions(self) -> list[str]:
        """Return no ZIP-confirmed local jurisdictions."""
        return []

    def get_zips_for_jurisdiction(self, jurisdiction_id: str) -> list[str]:
        """Return no ZIP prefixes because ZIP does not establish a city."""
        return []

    def reload(self) -> None:
        """Force reload of mappings from file."""
        self._loaded = False
        self._zip_mappings = {}
        self._state_mappings = {}
        self._load_mappings()
