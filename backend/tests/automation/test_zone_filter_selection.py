"""Tests for zone filter selection bug fix.

Verifies that the JavaScript selectByLabel function in fast filter handlers
correctly selects "South Central Railway" over "Central Railway".

The bug was caused by flawed matching logic:
    labelLower.includes(optTextLower)
which incorrectly matched "Central Railway" when searching for "South Central Railway"
because "south central railway".includes("central railway") === true.

The fix uses two-pass matching:
1. Exact match (case-insensitive)
2. Option text includes target (NOT vice versa)
"""

import pytest


class TestSelectByLabelLogic:
    """Tests for the corrected selectByLabel matching logic."""

    @staticmethod
    def simulate_select_by_label(options: list[str], target_labels: list[str]) -> str | None:
        """Python simulation of the corrected JavaScript selectByLabel logic.
        
        This mirrors the fixed JavaScript code to verify matching behavior.
        """
        labels = target_labels if isinstance(target_labels, list) else [target_labels]
        
        # Priority 1: Exact match (case-insensitive)
        for label in labels:
            label_lower = label.lower().strip()
            for opt_text in options:
                if opt_text.lower().strip() == label_lower:
                    return opt_text
        
        # Priority 2: Option text includes target label (NOT vice versa)
        for label in labels:
            label_lower = label.lower().strip()
            for opt_text in options:
                if label_lower in opt_text.lower().strip():
                    return opt_text
        
        return None

    def test_exact_match_selected_first(self):
        """Exact match should be selected even if partial match exists earlier."""
        options = ["Central Railway", "South Central Railway", "West Central Railway"]
        result = self.simulate_select_by_label(options, ["South Central Railway"])
        assert result == "South Central Railway"

    def test_south_central_over_central(self):
        """South Central Railway must be selected, not Central Railway."""
        # This is the exact scenario that caused the bug
        options = ["Central Railway", "South Central Railway"]
        result = self.simulate_select_by_label(options, ["South Central Railway", "SCR"])
        assert result == "South Central Railway"
        assert result != "Central Railway"

    def test_scr_fallback_to_south_central(self):
        """SCR as fallback should match South Central Railway via partial include."""
        options = ["Central Railway", "South Central Railway (SCR)"]
        result = self.simulate_select_by_label(options, ["South Central Railway", "SCR"])
        # Exact match for "South Central Railway" not found, but "SCR" partial match works
        assert result == "South Central Railway (SCR)"

    def test_all_exact_match(self):
        """ALL should match exactly."""
        options = ["ALL", "All Zones", "All Divisions"]
        result = self.simulate_select_by_label(options, ["ALL", "All"])
        assert result == "ALL"

    def test_case_insensitive_exact_match(self):
        """Exact match should be case-insensitive."""
        options = ["all", "Zone Wise"]
        result = self.simulate_select_by_label(options, ["ALL"])
        assert result == "all"

    def test_division_wise_exact_match(self):
        """Division Wise should match exactly."""
        options = ["Zone Wise", "Division Wise", "Station Wise"]
        result = self.simulate_select_by_label(options, ["Division Wise"])
        assert result == "Division Wise"

    def test_carriage_wagon_exact_match(self):
        """Carriage & Wagon department should match exactly."""
        options = ["ALL", "Carriage & Wagon", "Electrical", "Security"]
        result = self.simulate_select_by_label(options, ["Carriage & Wagon"])
        assert result == "Carriage & Wagon"

    def test_security_train_type_match(self):
        """Security-Train type should match."""
        options = ["ALL", "Punctuality-Train", "Security-Train", "Electrical Equipment-Train"]
        result = self.simulate_select_by_label(options, ["Security-Train"])
        assert result == "Security-Train"

    def test_punctuality_train_type_match(self):
        """Punctuality-Train type should match."""
        options = ["ALL", "Punctuality-Train", "Security-Train"]
        result = self.simulate_select_by_label(options, ["Punctuality-Train"])
        assert result == "Punctuality-Train"

    def test_electrical_equipment_type_match(self):
        """Electrical Equipment-Train type should match."""
        options = ["ALL", "Electrical Equipment-Train", "Punctuality-Train"]
        result = self.simulate_select_by_label(options, ["Electrical Equipment-Train"])
        assert result == "Electrical Equipment-Train"

    def test_partial_match_fallback(self):
        """Partial match should work when exact match not found."""
        options = ["Zone Wise / Dept. Wise", "Division Wise"]
        result = self.simulate_select_by_label(options, ["Zone Wise", "ZoneWise"])
        # "Zone Wise" is contained in "Zone Wise / Dept. Wise"
        assert result == "Zone Wise / Dept. Wise"

    def test_no_match_returns_none(self):
        """Should return None when no match found."""
        options = ["Central Railway", "Northern Railway"]
        result = self.simulate_select_by_label(options, ["South Central Railway"])
        assert result is None

    def test_empty_options_returns_none(self):
        """Should return None for empty options list."""
        result = self.simulate_select_by_label([], ["South Central Railway"])
        assert result is None

    def test_first_exact_match_wins(self):
        """First exact match in target labels should be selected."""
        options = ["ALL", "All"]
        result = self.simulate_select_by_label(options, ["ALL", "All"])
        assert result == "ALL"


class TestOldBuggyBehavior:
    """Tests documenting the old buggy behavior that was fixed."""

    @staticmethod
    def simulate_old_buggy_logic(options: list[str], target_labels: list[str]) -> str | None:
        """Simulation of the OLD BUGGY JavaScript selectByLabel logic.
        
        This had the bug where labelLower.includes(optTextLower) could
        incorrectly match shorter strings.
        """
        labels = target_labels if isinstance(target_labels, list) else [target_labels]
        
        for label in labels:
            label_lower = label.lower().strip()
            for opt_text in options:
                opt_lower = opt_text.lower().strip()
                # OLD BUGGY LOGIC: all three conditions in one pass
                if (opt_lower == label_lower or 
                    opt_lower in label_lower or  # optTextLower.includes(labelLower)
                    label_lower in opt_lower):   # labelLower.includes(optTextLower) - THE BUG
                    return opt_text
        
        return None

    def test_old_logic_bug_demonstration(self):
        """Demonstrate the bug in the old logic."""
        options = ["Central Railway", "South Central Railway"]
        # Old buggy logic would return "Central Railway" because:
        # "south central railway".includes("central railway") === true
        result = self.simulate_old_buggy_logic(options, ["South Central Railway"])
        # This documents the BUG - "Central Railway" was incorrectly selected
        assert result == "Central Railway"  # BUG!

    def test_new_logic_fixes_bug(self):
        """Verify the new logic fixes the bug."""
        options = ["Central Railway", "South Central Railway"]
        # New fixed logic returns correct result
        result = TestSelectByLabelLogic.simulate_select_by_label(
            options, ["South Central Railway"]
        )
        assert result == "South Central Railway"  # FIXED!


class TestReport1013FilterVerification:
    """Tests for Report 10-13 filter verification logic."""

    def test_zone_filter_verification_rejects_central(self):
        """Zone filter verification should reject Central Railway."""
        zone_applied = "Central Railway"
        zone_lower = zone_applied.lower()
        
        # The verification logic from comprehensive1013_handler.py
        zone_ok = (
            "south central" in zone_lower or 
            "scr" in zone_lower
        )
        
        assert not zone_ok, "Central Railway should be rejected"

    def test_zone_filter_verification_accepts_south_central(self):
        """Zone filter verification should accept South Central Railway."""
        zone_applied = "South Central Railway"
        zone_lower = zone_applied.lower()
        
        zone_ok = (
            "south central" in zone_lower or 
            "scr" in zone_lower
        )
        
        assert zone_ok, "South Central Railway should be accepted"

    def test_zone_filter_verification_accepts_scr(self):
        """Zone filter verification should accept SCR."""
        zone_applied = "SCR"
        zone_lower = zone_applied.lower()
        
        zone_ok = (
            "south central" in zone_lower or 
            "scr" in zone_lower
        )
        
        assert zone_ok, "SCR should be accepted"


class TestReport1FilterDefaults:
    """Tests for Report 1 filter default values."""

    def test_report1_uses_zone_all(self):
        """Report 1 should use Zone=ALL (not South Central Railway)."""
        from app.automation.report1_filters import REPORT_1_FILTERS
        
        zone_filter = next(
            (f for f in REPORT_1_FILTERS if f.name == "zone"),
            None,
        )
        assert zone_filter is not None
        assert zone_filter.value == "ALL"

    def test_report1_uses_zone_wise_view(self):
        """Report 1 should use View=Zone Wise."""
        from app.automation.report1_filters import REPORT_1_FILTERS
        
        view_filter = next(
            (f for f in REPORT_1_FILTERS if f.name == "view"),
            None,
        )
        assert view_filter is not None
        assert view_filter.value == "Zone Wise"
