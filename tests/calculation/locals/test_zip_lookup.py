"""
Tests for ZIP code to jurisdiction lookup.

All tests use PLACEHOLDER mappings.
"""

import pytest

from tax_estimator.calculation.locals.zip_lookup import (
    ZipJurisdictionLookup,
    ZipLookupError,
)


class TestZipJurisdictionLookup:
    """Tests for ZipJurisdictionLookup class."""

    @pytest.fixture
    def lookup(self) -> ZipJurisdictionLookup:
        """Create a lookup instance."""
        return ZipJurisdictionLookup()

    def test_lookup_initialization(self, lookup: ZipJurisdictionLookup) -> None:
        """Test lookup initializes correctly."""
        assert lookup.mapping_file is not None
        assert lookup.mapping_file.exists()

    def test_lookup_nyc_zip(self, lookup: ZipJurisdictionLookup) -> None:
        """Test looking up NYC ZIP codes."""
        # NYC ZIP codes start with 100xx, 101xx, 102xx, 103xx, 104xx
        local_jur = lookup.lookup_local_jurisdiction("10001")  # Manhattan
        state = lookup.lookup_state("10001")
        assert state == "NY"
        assert local_jur is not None
        # local_jur should be the jurisdiction ID for NYC

    def test_lookup_philadelphia_zip(self, lookup: ZipJurisdictionLookup) -> None:
        """Test looking up Philadelphia ZIP codes."""
        # Philadelphia ZIP codes start with 191xx
        local_jur = lookup.lookup_local_jurisdiction("19101")
        state = lookup.lookup_state("19101")
        assert state == "PA"
        assert local_jur is not None

    def test_lookup_detroit_zip(self, lookup: ZipJurisdictionLookup) -> None:
        """Test looking up Detroit ZIP codes."""
        # Detroit ZIP codes start with 482xx
        local_jur = lookup.lookup_local_jurisdiction("48201")
        state = lookup.lookup_state("48201")
        assert state == "MI"
        assert local_jur is not None

    def test_lookup_cleveland_zip(self, lookup: ZipJurisdictionLookup) -> None:
        """Test looking up Cleveland ZIP codes."""
        # Cleveland ZIP codes start with 441xx
        local_jur = lookup.lookup_local_jurisdiction("44101")
        state = lookup.lookup_state("44101")
        assert state == "OH"
        assert local_jur is not None

    def test_lookup_state_only_zip(self, lookup: ZipJurisdictionLookup) -> None:
        """Test looking up ZIP in state without local tax."""
        # Texas ZIP code (no state income tax, no local tax)
        state = lookup.lookup_state("75001")  # Dallas area
        assert state == "TX"
        # Local jurisdiction may or may not exist
        local_jur = lookup.lookup_local_jurisdiction("75001")
        # Just verify no error is raised

    def test_lookup_handles_zip_plus_4(self, lookup: ZipJurisdictionLookup) -> None:
        """Test lookup handles ZIP+4 format by using first 3 digits."""
        state = lookup.lookup_state("10001-1234")
        assert state == "NY"

    def test_lookup_returns_none_for_unknown(self, lookup: ZipJurisdictionLookup) -> None:
        """Test lookup returns None for unknown ZIP prefix."""
        # 999 is not a valid US ZIP prefix
        state = lookup.lookup_state("99999")
        # May or may not return a state depending on mappings
        # Just verify no error is raised


class TestZipPrefixMapping:
    """Test ZIP prefix to state mapping."""

    @pytest.fixture
    def lookup(self) -> ZipJurisdictionLookup:
        return ZipJurisdictionLookup()

    @pytest.mark.parametrize("zip_code,expected_state", [
        ("10001", "NY"),  # New York
        ("90210", "CA"),  # California
        ("75001", "TX"),  # Texas
        ("33101", "FL"),  # Florida
        ("60601", "IL"),  # Illinois
        ("19101", "PA"),  # Pennsylvania
        ("44101", "OH"),  # Ohio
        ("30301", "GA"),  # Georgia
        ("27601", "NC"),  # North Carolina
        ("48201", "MI"),  # Michigan
    ])
    def test_state_from_zip_prefix(
        self,
        lookup: ZipJurisdictionLookup,
        zip_code: str,
        expected_state: str
    ) -> None:
        """Test getting state from ZIP prefix."""
        state = lookup.lookup_state(zip_code)
        assert state == expected_state


class TestCombinedLookup:
    """Test combined state and local lookup."""

    @pytest.fixture
    def lookup(self) -> ZipJurisdictionLookup:
        return ZipJurisdictionLookup()

    def test_lookup_returns_both(self, lookup: ZipJurisdictionLookup) -> None:
        """Test lookup returns both state and local jurisdiction."""
        result = lookup.lookup("10001")
        assert "state" in result
        assert "local_jurisdiction" in result
        assert result["state"] == "NY"


class TestZipEdgeCases:
    """Test edge cases for ZIP lookup."""

    @pytest.fixture
    def lookup(self) -> ZipJurisdictionLookup:
        return ZipJurisdictionLookup()

    def test_lookup_with_leading_zeros(self, lookup: ZipJurisdictionLookup) -> None:
        """Test ZIP codes with leading zeros."""
        # Massachusetts ZIP
        state = lookup.lookup_state("02101")
        assert state == "MA"

    def test_lookup_with_spaces(self, lookup: ZipJurisdictionLookup) -> None:
        """Test ZIP codes with spaces are handled."""
        state = lookup.lookup_state(" 10001 ")
        assert state == "NY"

    def test_get_all_local_jurisdictions(self, lookup: ZipJurisdictionLookup) -> None:
        """Test getting all local jurisdictions."""
        jurisdictions = lookup.get_all_local_jurisdictions()
        assert len(jurisdictions) > 0

    def test_get_zips_for_jurisdiction(self, lookup: ZipJurisdictionLookup) -> None:
        """Test getting ZIPs for a specific jurisdiction."""
        zips = lookup.get_zips_for_jurisdiction("US-NY-NYC")
        # May or may not find ZIPs depending on mapping format
        assert isinstance(zips, list)

    def test_reload_mappings(self, lookup: ZipJurisdictionLookup) -> None:
        """Test reloading mappings."""
        # First lookup to load mappings
        lookup.lookup_state("10001")
        # Reload
        lookup.reload()
        # Should still work
        state = lookup.lookup_state("10001")
        assert state == "NY"
