"""Tests for the deterministic validation engine."""

import pytest

from app.services.validation import ValidationEngine


@pytest.fixture
def engine():
    return ValidationEngine()


class TestRequiredFields:
    def test_missing_required_field(self, engine):
        record = {"village": "TestVillage", "district": "TestDistrict"}
        issues = engine.validate(record)
        failed = [i for i in issues if i.status == "failed" and i.field_name == "survey_number"]
        assert len(failed) == 1

    def test_all_required_present(self, engine):
        record = {
            "survey_number": "123/4",
            "village": "TestVillage",
            "district": "TestDistrict",
        }
        issues = engine.validate(record)
        failed_required = [
            i for i in issues
            if i.rule_name == "required_field" and i.status == "failed"
        ]
        assert len(failed_required) == 0


class TestAreaValidation:
    def test_negative_area(self, engine):
        record = {"survey_number": "1", "village": "V", "district": "D", "area": -5}
        issues = engine.validate(record)
        area_issues = [i for i in issues if i.field_name == "area" and i.status == "failed"]
        assert len(area_issues) == 1

    def test_non_numeric_area(self, engine):
        record = {"survey_number": "1", "village": "V", "district": "D", "area": "abc"}
        issues = engine.validate(record)
        area_issues = [i for i in issues if i.field_name == "area" and i.status == "failed"]
        assert len(area_issues) == 1

    def test_valid_area(self, engine):
        record = {"survey_number": "1", "village": "V", "district": "D", "area": 2.5, "area_unit": "hectare"}
        issues = engine.validate(record)
        area_failed = [i for i in issues if i.field_name == "area" and i.status == "failed"]
        assert len(area_failed) == 0

    def test_unknown_area_unit(self, engine):
        record = {"survey_number": "1", "village": "V", "district": "D", "area": 2.5, "area_unit": "foobar"}
        issues = engine.validate(record)
        unit_warnings = [i for i in issues if i.field_name == "area_unit" and i.status == "warning"]
        assert len(unit_warnings) == 1


class TestOwnershipPercentage:
    def test_over_100(self, engine):
        record = {"survey_number": "1", "village": "V", "district": "D", "ownership_percentage": 150}
        issues = engine.validate(record)
        pct_issues = [i for i in issues if i.field_name == "ownership_percentage" and i.status == "failed"]
        assert len(pct_issues) == 1


class TestDateValidation:
    def test_future_date(self, engine):
        record = {"survey_number": "1", "village": "V", "district": "D", "mutation_date": "2099-01-01"}
        issues = engine.validate(record)
        date_issues = [i for i in issues if i.field_name == "mutation_date" and i.status == "failed"]
        assert len(date_issues) == 1

    def test_invalid_date_format(self, engine):
        record = {"survey_number": "1", "village": "V", "district": "D", "registration_date": "not-a-date"}
        issues = engine.validate(record)
        date_issues = [i for i in issues if i.field_name == "registration_date" and i.status == "warning"]
        assert len(date_issues) == 1
