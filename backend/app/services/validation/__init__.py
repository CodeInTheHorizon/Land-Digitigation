"""Deterministic validation engine for land records.

Validates extracted and mapped land record fields against a
comprehensive rule set before any LLM-based validation.

Rules produce PASS / WARNING / FAIL / REVIEW_REQUIRED verdicts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


class ValidationStatus:
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    REVIEW_REQUIRED = "review_required"


class RuleType:
    FORMAT = "format"
    RANGE = "range"
    REQUIRED = "required"
    CONSISTENCY = "consistency"
    CROSS_REFERENCE = "cross_reference"


@dataclass
class ValidationIssue:
    rule_name: str
    rule_type: str  # format | range | required | consistency | cross_reference
    field_name: Optional[str]
    status: str  # passed | failed | warning | review_required
    message: str
    severity: str = "medium"  # low | medium | high | critical
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Aggregated validation result for a record."""

    issues: List[ValidationIssue] = field(default_factory=list)
    status: str = "pending"  # passed | failed | warning | review_required
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    review_count: int = 0

    @property
    def is_valid(self) -> bool:
        return self.failed_count == 0

    @property
    def needs_review(self) -> bool:
        return self.review_count > 0

    def compute_status(self) -> str:
        """Compute overall status from issue counts."""
        self.passed_count = sum(1 for i in self.issues if i.status == ValidationStatus.PASSED)
        self.failed_count = sum(1 for i in self.issues if i.status == ValidationStatus.FAILED)
        self.warning_count = sum(1 for i in self.issues if i.status == ValidationStatus.WARNING)
        self.review_count = sum(1 for i in self.issues if i.status == ValidationStatus.REVIEW_REQUIRED)

        if self.failed_count > 0:
            self.status = ValidationStatus.FAILED
        elif self.review_count > 0:
            self.status = ValidationStatus.REVIEW_REQUIRED
        elif self.warning_count > 0:
            self.status = ValidationStatus.WARNING
        else:
            self.status = ValidationStatus.PASSED
        return self.status


class ValidationEngine:
    """Deterministic rule-based validation for extracted land records.

    This runs BEFORE any LLM-based validation to catch obvious issues cheaply.
    Thread-safe and stateless.
    """

    REQUIRED_FIELDS = [
        "survey_number",
        "village",
        "district",
    ]

    AREA_UNITS = {
        "hectare", "acre", "bigha", "sq_meter", "sq_feet",
        "guntha", "kanal", "marla", "dismil",
    }

    LAND_CLASSIFICATIONS = {
        "agricultural", "residential", "commercial", "industrial",
        "barren", "forest", "govt", "wetland", "pasture",
    }

    OWNERSHIP_TYPES = {
        "sole", "joint", "inherited", "leased", "government",
    }

    # Area range limits by unit (min, max) — sanity checks
    AREA_RANGES = {
        "hectare": (0.001, 50000),
        "acre": (0.001, 125000),
        "bigha": (0.001, 200000),
        "sq_meter": (1, 500000000),
        "sq_feet": (10, 5000000000),
        "guntha": (0.01, 500000),
        "kanal": (0.01, 250000),
        "marla": (0.1, 5000000),
    }

    # Indian states for validation
    INDIAN_STATES = {
        "andhra pradesh", "arunachal pradesh", "assam", "bihar",
        "chhattisgarh", "goa", "gujarat", "haryana", "himachal pradesh",
        "jharkhand", "karnataka", "kerala", "madhya pradesh",
        "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland",
        "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
        "telangana", "tripura", "uttar pradesh", "uttarakhand",
        "west bengal", "delhi", "jammu and kashmir", "ladakh",
        "chandigarh", "puducherry", "lakshadweep",
        "dadra and nagar haveli and daman and diu",
        "andaman and nicobar islands",
    }

    def validate(self, record: Dict[str, Any]) -> ValidationResult:
        """Run all deterministic validation rules on a record.

        Parameters
        ----------
        record : dict
            Flat dict of field_name → value from the FieldMapper.

        Returns
        -------
        ValidationResult with all issues and computed status.
        """
        result = ValidationResult()

        result.issues.extend(self._check_required_fields(record))
        result.issues.extend(self._check_area(record))
        result.issues.extend(self._check_survey_number_format(record))
        result.issues.extend(self._check_date_fields(record))
        result.issues.extend(self._check_ownership_percentage(record))
        result.issues.extend(self._check_enum_fields(record))
        result.issues.extend(self._check_location_hierarchy(record))
        result.issues.extend(self._check_person_fields(record))
        result.issues.extend(self._check_amount_fields(record))
        result.issues.extend(self._check_confidence_thresholds(record))

        result.compute_status()
        return result

    def _check_required_fields(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        for fld in self.REQUIRED_FIELDS:
            value = record.get(fld)
            if not value or (isinstance(value, str) and not value.strip()):
                issues.append(ValidationIssue(
                    rule_name="required_field",
                    rule_type=RuleType.REQUIRED,
                    field_name=fld,
                    status=ValidationStatus.FAILED,
                    message=f"Required field '{fld}' is missing or empty",
                    severity="high",
                ))
            else:
                issues.append(ValidationIssue(
                    rule_name="required_field",
                    rule_type=RuleType.REQUIRED,
                    field_name=fld,
                    status=ValidationStatus.PASSED,
                    message=f"Required field '{fld}' is present",
                    severity="low",
                ))
        return issues

    def _check_area(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        area = record.get("area")
        area_unit = record.get("area_unit")

        if area is not None:
            try:
                area_val = float(area)
                if area_val <= 0:
                    issues.append(ValidationIssue(
                        rule_name="area_positive",
                        rule_type=RuleType.RANGE,
                        field_name="area",
                        status=ValidationStatus.FAILED,
                        message="Area must be a positive number",
                        severity="high",
                    ))
                else:
                    # Check against unit-specific range
                    if area_unit and area_unit.lower() in self.AREA_RANGES:
                        min_val, max_val = self.AREA_RANGES[area_unit.lower()]
                        if area_val > max_val:
                            issues.append(ValidationIssue(
                                rule_name="area_range",
                                rule_type=RuleType.RANGE,
                                field_name="area",
                                status=ValidationStatus.WARNING,
                                message=f"Area {area_val} {area_unit} exceeds typical maximum ({max_val})",
                                severity="medium",
                                details={"area": area_val, "unit": area_unit, "max": max_val},
                            ))
                        elif area_val < min_val:
                            issues.append(ValidationIssue(
                                rule_name="area_range",
                                rule_type=RuleType.RANGE,
                                field_name="area",
                                status=ValidationStatus.WARNING,
                                message=f"Area {area_val} {area_unit} is unusually small (min {min_val})",
                                severity="medium",
                                details={"area": area_val, "unit": area_unit, "min": min_val},
                            ))
                        else:
                            issues.append(ValidationIssue(
                                rule_name="area_range",
                                rule_type=RuleType.RANGE,
                                field_name="area",
                                status=ValidationStatus.PASSED,
                                message="Area is within expected range",
                                severity="low",
                            ))
                    elif area_val > 100000:
                        issues.append(ValidationIssue(
                            rule_name="area_range",
                            rule_type=RuleType.RANGE,
                            field_name="area",
                            status=ValidationStatus.WARNING,
                            message=f"Unusually large area: {area_val}",
                            severity="medium",
                        ))
            except (TypeError, ValueError):
                issues.append(ValidationIssue(
                    rule_name="area_numeric",
                    rule_type=RuleType.FORMAT,
                    field_name="area",
                    status=ValidationStatus.FAILED,
                    message=f"Area is not a valid number: {area}",
                    severity="high",
                ))

        if area_unit and area_unit.lower() not in self.AREA_UNITS:
            issues.append(ValidationIssue(
                rule_name="area_unit_valid",
                rule_type=RuleType.FORMAT,
                field_name="area_unit",
                status=ValidationStatus.WARNING,
                message=f"Unknown area unit: {area_unit}",
                severity="medium",
            ))

        # Consistency: area without unit
        if area is not None and not area_unit:
            issues.append(ValidationIssue(
                rule_name="area_unit_present",
                rule_type=RuleType.CONSISTENCY,
                field_name="area",
                status=ValidationStatus.REVIEW_REQUIRED,
                message="Area value found but no unit specified",
                severity="medium",
            ))

        return issues

    def _check_survey_number_format(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        for fld in ("survey_number", "khasra_number", "khata_number", "plot_number"):
            val = record.get(fld)
            if val and isinstance(val, str):
                # Check for unusual characters
                if not re.match(r"^[\d/\-A-Za-z\s.]+$", val):
                    issues.append(ValidationIssue(
                        rule_name=f"{fld}_format",
                        rule_type=RuleType.FORMAT,
                        field_name=fld,
                        status=ValidationStatus.WARNING,
                        message=f"{fld} contains unusual characters: {val}",
                        severity="medium",
                    ))
                # Check reasonable length
                if len(val) > 50:
                    issues.append(ValidationIssue(
                        rule_name=f"{fld}_length",
                        rule_type=RuleType.FORMAT,
                        field_name=fld,
                        status=ValidationStatus.REVIEW_REQUIRED,
                        message=f"{fld} is unusually long ({len(val)} chars) — possible extraction error",
                        severity="medium",
                    ))
        return issues

    def _check_date_fields(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        today = date.today()

        for fld in ("mutation_date", "registration_date"):
            val = record.get(fld)
            if val:
                if isinstance(val, str):
                    try:
                        parsed = datetime.strptime(val, "%Y-%m-%d").date()
                        if parsed > today:
                            issues.append(ValidationIssue(
                                rule_name=f"{fld}_future",
                                rule_type=RuleType.RANGE,
                                field_name=fld,
                                status=ValidationStatus.FAILED,
                                message=f"{fld} is in the future: {val}",
                                severity="high",
                            ))
                        elif parsed.year < 1800:
                            issues.append(ValidationIssue(
                                rule_name=f"{fld}_too_old",
                                rule_type=RuleType.RANGE,
                                field_name=fld,
                                status=ValidationStatus.REVIEW_REQUIRED,
                                message=f"{fld} is very old ({parsed.year}) — verify accuracy",
                                severity="medium",
                            ))
                        else:
                            issues.append(ValidationIssue(
                                rule_name=f"{fld}_valid",
                                rule_type=RuleType.RANGE,
                                field_name=fld,
                                status=ValidationStatus.PASSED,
                                message=f"{fld} is a valid date",
                                severity="low",
                            ))
                    except ValueError:
                        issues.append(ValidationIssue(
                            rule_name=f"{fld}_format",
                            rule_type=RuleType.FORMAT,
                            field_name=fld,
                            status=ValidationStatus.WARNING,
                            message=f"Cannot parse date: {val}",
                            severity="medium",
                        ))
        return issues

    def _check_ownership_percentage(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []

        # Single ownership percentage
        pct = record.get("ownership_percentage")
        if pct is not None:
            try:
                pct_val = float(pct)
                if not (0 < pct_val <= 100):
                    issues.append(ValidationIssue(
                        rule_name="ownership_pct_range",
                        rule_type=RuleType.RANGE,
                        field_name="ownership_percentage",
                        status=ValidationStatus.FAILED,
                        message=f"Ownership percentage out of range: {pct_val}",
                        severity="high",
                    ))
            except (TypeError, ValueError):
                pass

        # Multiple owners: percentages should sum to 100
        owners = record.get("owners", [])
        if isinstance(owners, list) and len(owners) > 1:
            pct_sum = 0.0
            has_pct = False
            for owner in owners:
                if isinstance(owner, dict) and "ownership_percentage" in owner:
                    try:
                        pct_sum += float(owner["ownership_percentage"])
                        has_pct = True
                    except (TypeError, ValueError):
                        pass
            if has_pct and abs(pct_sum - 100.0) > 0.5:
                issues.append(ValidationIssue(
                    rule_name="ownership_pct_sum",
                    rule_type=RuleType.CONSISTENCY,
                    field_name="ownership_percentage",
                    status=ValidationStatus.FAILED,
                    message=f"Ownership percentages sum to {pct_sum}%, expected 100%",
                    severity="critical",
                    details={"sum": pct_sum},
                ))

        return issues

    def _check_enum_fields(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        lc = record.get("land_classification")
        if lc and lc.lower() not in self.LAND_CLASSIFICATIONS:
            issues.append(ValidationIssue(
                rule_name="land_classification_valid",
                rule_type=RuleType.FORMAT,
                field_name="land_classification",
                status=ValidationStatus.WARNING,
                message=f"Unknown land classification: {lc}",
                severity="low",
            ))

        ot = record.get("ownership_type")
        if ot and ot.lower() not in self.OWNERSHIP_TYPES:
            issues.append(ValidationIssue(
                rule_name="ownership_type_valid",
                rule_type=RuleType.FORMAT,
                field_name="ownership_type",
                status=ValidationStatus.WARNING,
                message=f"Unknown ownership type: {ot}",
                severity="low",
            ))
        return issues

    def _check_location_hierarchy(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        """Check that location fields form a valid hierarchy."""
        issues = []
        village = record.get("village")
        tehsil = record.get("tehsil")
        district = record.get("district")
        state = record.get("state")

        # Village without district
        if village and not district:
            issues.append(ValidationIssue(
                rule_name="location_hierarchy",
                rule_type=RuleType.CONSISTENCY,
                field_name="village",
                status=ValidationStatus.WARNING,
                message="Village specified without district",
                severity="medium",
            ))

        # State validation
        if state and state.lower() not in self.INDIAN_STATES:
            issues.append(ValidationIssue(
                rule_name="state_valid",
                rule_type=RuleType.FORMAT,
                field_name="state",
                status=ValidationStatus.REVIEW_REQUIRED,
                message=f"Unrecognized state: {state}",
                severity="medium",
            ))

        # Same name at different levels (likely extraction error)
        names = [n.lower().strip() for n in [village, tehsil, district] if n]
        if len(names) != len(set(names)):
            issues.append(ValidationIssue(
                rule_name="location_duplicates",
                rule_type=RuleType.CONSISTENCY,
                field_name="village",
                status=ValidationStatus.REVIEW_REQUIRED,
                message="Same name appears at multiple location levels — possible extraction error",
                severity="high",
            ))

        return issues

    def _check_person_fields(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate person/owner name fields."""
        issues = []
        persons = record.get("persons", [])
        if isinstance(persons, list):
            for i, person in enumerate(persons):
                if isinstance(person, dict):
                    name = person.get("name", "")
                    if name and len(name) < 2:
                        issues.append(ValidationIssue(
                            rule_name="person_name_length",
                            rule_type=RuleType.FORMAT,
                            field_name=f"person_{i}_name",
                            status=ValidationStatus.WARNING,
                            message=f"Person name is very short: '{name}'",
                            severity="medium",
                        ))
                    if name and len(name) > 200:
                        issues.append(ValidationIssue(
                            rule_name="person_name_length",
                            rule_type=RuleType.FORMAT,
                            field_name=f"person_{i}_name",
                            status=ValidationStatus.REVIEW_REQUIRED,
                            message=f"Person name is unusually long ({len(name)} chars)",
                            severity="medium",
                        ))
        return issues

    def _check_amount_fields(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate monetary amount fields."""
        issues = []
        for fld in ("consideration_amount", "stamp_duty"):
            val = record.get(fld)
            if val is not None:
                try:
                    amt = float(val)
                    if amt < 0:
                        issues.append(ValidationIssue(
                            rule_name=f"{fld}_positive",
                            rule_type=RuleType.RANGE,
                            field_name=fld,
                            status=ValidationStatus.FAILED,
                            message=f"{fld} cannot be negative: {amt}",
                            severity="high",
                        ))
                    if amt > 10_000_000_000:  # 10 billion
                        issues.append(ValidationIssue(
                            rule_name=f"{fld}_range",
                            rule_type=RuleType.RANGE,
                            field_name=fld,
                            status=ValidationStatus.REVIEW_REQUIRED,
                            message=f"{fld} is unusually large: {amt}",
                            severity="medium",
                        ))
                except (TypeError, ValueError):
                    issues.append(ValidationIssue(
                        rule_name=f"{fld}_numeric",
                        rule_type=RuleType.FORMAT,
                        field_name=fld,
                        status=ValidationStatus.FAILED,
                        message=f"{fld} is not a valid number: {val}",
                        severity="high",
                    ))

        # Cross-check: stamp duty should be less than consideration
        consideration = record.get("consideration_amount")
        stamp = record.get("stamp_duty")
        if consideration is not None and stamp is not None:
            try:
                c_val = float(consideration)
                s_val = float(stamp)
                if c_val > 0 and s_val > c_val:
                    issues.append(ValidationIssue(
                        rule_name="stamp_vs_consideration",
                        rule_type=RuleType.CONSISTENCY,
                        field_name="stamp_duty",
                        status=ValidationStatus.REVIEW_REQUIRED,
                        message=f"Stamp duty ({s_val}) exceeds consideration amount ({c_val})",
                        severity="high",
                    ))
            except (TypeError, ValueError):
                pass

        return issues

    def _check_confidence_thresholds(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        """Flag fields with low confidence for human review."""
        issues = []
        field_confidences = record.get("field_confidences")
        if isinstance(field_confidences, dict):
            for fld, conf_data in field_confidences.items():
                composite = conf_data if isinstance(conf_data, (int, float)) else conf_data.get("composite", 1.0)
                if composite < 0.4:
                    issues.append(ValidationIssue(
                        rule_name="low_confidence",
                        rule_type=RuleType.CROSS_REFERENCE,
                        field_name=fld,
                        status=ValidationStatus.REVIEW_REQUIRED,
                        message=f"Field '{fld}' has low confidence ({composite:.2%}) — needs human review",
                        severity="high",
                        details={"confidence": composite},
                    ))
                elif composite < 0.6:
                    issues.append(ValidationIssue(
                        rule_name="moderate_confidence",
                        rule_type=RuleType.CROSS_REFERENCE,
                        field_name=fld,
                        status=ValidationStatus.WARNING,
                        message=f"Field '{fld}' has moderate confidence ({composite:.2%})",
                        severity="medium",
                        details={"confidence": composite},
                    ))
        return issues
