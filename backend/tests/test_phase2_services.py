"""Comprehensive unit tests for Phase 2 — Intelligent Extraction & Validation.

Tests cover:
  1. DocumentClassifier (10 categories, multi-signal scoring)
  2. EntityExtractor (18+ entity types, deduplication, multi-page merge)
  3. FieldNormalizer (dates, names, Devanagari digits, area units)
  4. FieldMapper (entity→field mapping, conflict resolution, provenance)
  5. ConfidenceEngine (5-signal composite scoring)
  6. ValidationEngine (deterministic rules, all severity levels)
  7. ExtractionPipeline (end-to-end orchestration)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


# ============================================================================
# 1. DocumentClassifier
# ============================================================================

from app.services.classifier.document_classifier import (
    ClassificationResult,
    DocumentCategory,
    DocumentClassifier,
)


class TestDocumentClassifier:
    """Tests for the multi-signal document classifier."""

    def setup_method(self):
        self.classifier = DocumentClassifier()

    # -- Basic classification --

    def test_empty_text_returns_miscellaneous(self):
        result = self.classifier.classify("")
        assert result.category == DocumentCategory.MISCELLANEOUS
        assert result.confidence == 0.0

    def test_whitespace_only_returns_miscellaneous(self):
        result = self.classifier.classify("   \n\t  ")
        assert result.category == DocumentCategory.MISCELLANEOUS
        assert result.confidence == 0.0

    def test_classify_sale_deed(self):
        text = """
        SALE DEED
        This deed of sale is executed between the buyer and seller.
        The vendor agrees to sell the property for a consideration amount
        of Rs. 50,00,000. Stamp duty paid. Witness 1, Witness 2.
        """
        result = self.classifier.classify(text)
        assert result.category == DocumentCategory.SALE_DEED
        assert result.confidence > 0.5
        assert "sale deed" in [k.lower() for k in result.matched_keywords] or len(result.matched_headers) > 0

    def test_classify_khasra(self):
        text = """
        KHASRA GIRDAWARI REGISTER
        Khasra Number: 123/4
        Village: Ramnagar, Tehsil: Sadar, District: Lucknow
        Rabi crop season, fasal inspection completed.
        """
        result = self.classifier.classify(text)
        assert result.category == DocumentCategory.KHASRA
        assert result.confidence > 0.5

    def test_classify_mutation(self):
        text = """
        MUTATION ORDER - DAKHIL KHARIJ
        Transfer of ownership from Ram Prasad to Suresh Kumar.
        Mutation register entry. Inheritance succession partition.
        """
        result = self.classifier.classify(text)
        assert result.category == DocumentCategory.MUTATION
        assert result.confidence > 0.5

    def test_classify_registration(self):
        text = """
        REGISTERED DOCUMENT
        Sub Registrar Office, Registration Number: 12345/2023
        Registration certificate issued. Registered on 15/03/2023.
        """
        result = self.classifier.classify(text)
        assert result.category == DocumentCategory.REGISTRATION
        assert result.confidence > 0.5

    def test_classify_khata(self):
        text = """
        KHATAUNI
        Khata Number: 456
        Khatauni Number: 789
        Account ledger entry.
        """
        result = self.classifier.classify(text)
        assert result.category == DocumentCategory.KHATA
        assert result.confidence > 0.5

    def test_classify_land_map(self):
        text = """
        SURVEY MAP
        Scale: 1:500. Tippan.
        North boundary: road
        South boundary: Ramesh's field
        East: canal
        West: government land
        """
        result = self.classifier.classify(text, page_count=1)
        assert result.category == DocumentCategory.LAND_MAP
        assert result.confidence > 0.5

    def test_classify_tax_revenue(self):
        text = """
        LAND REVENUE RECEIPT
        Tax receipt for lagaan payment.
        Amount: ₹5,000. Assessment year 2023-24.
        भू-राजस्व रसीद
        """
        result = self.classifier.classify(text)
        assert result.category == DocumentCategory.TAX_REVENUE
        assert result.confidence > 0.5

    def test_classify_hindi_land_ownership(self):
        text = """
        अधिकार अभिलेख
        जमाबंदी - स्वामित्व प्रमाण पत्र
        मालिक का नाम: रामेश्वर प्रसाद
        भूमि अधिकार पट्टा
        """
        result = self.classifier.classify(text)
        assert result.category == DocumentCategory.LAND_OWNERSHIP
        assert result.confidence > 0.5

    # -- Structural heuristics --

    def test_structural_bonus_khasra_crop_seasons(self):
        text = "khasra field data rabi kharif zaid"
        result = self.classifier.classify(text)
        assert result.scores.get("khasra", 0) > 0

    def test_structural_bonus_sale_deed_witnesses(self):
        text = "sale deed witness gawah witness stamp duty"
        result = self.classifier.classify(text)
        assert result.scores.get("sale_deed", 0) > 0

    # -- Score normalization --

    def test_scores_are_normalized_0_to_1(self):
        text = "survey number village district land record"
        result = self.classifier.classify(text)
        for score_val in result.scores.values():
            assert 0.0 <= score_val <= 1.0

    def test_result_has_all_categories_in_scores(self):
        text = "generic land document"
        result = self.classifier.classify(text)
        for cat in DocumentCategory:
            assert cat.value in result.scores


# ============================================================================
# 2. EntityExtractor
# ============================================================================

from app.services.nlp.entity_extractor import (
    EntityExtractor,
    EntitySpan,
    EntityType,
    ExtractionResult,
)


class TestEntityExtractor:
    """Tests for the regex-based entity extractor."""

    def setup_method(self):
        self.extractor = EntityExtractor()

    # -- Empty input --

    def test_empty_text(self):
        result = self.extractor.extract("")
        assert result.entity_count == 0
        assert result.text_length == 0

    def test_whitespace_text(self):
        result = self.extractor.extract("   \n  ")
        assert result.entity_count == 0

    # -- Survey / identification numbers --

    def test_extract_survey_number(self):
        text = "Survey No. 123/4A"
        result = self.extractor.extract(text, page_number=1)
        matches = result.by_type(EntityType.SURVEY_NUMBER)
        assert len(matches) >= 1
        assert "123/4A" in matches[0].value
        assert matches[0].page_number == 1

    def test_extract_khasra_number(self):
        text = "Khasra Number: 456/7"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.KHASRA_NUMBER)
        assert len(matches) >= 1
        assert "456/7" in matches[0].value

    def test_extract_khata_number(self):
        text = "Khata No: 89"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.KHATA_NUMBER)
        assert len(matches) >= 1

    def test_extract_plot_number(self):
        text = "Plot No. 12B"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.PLOT_NUMBER)
        assert len(matches) >= 1

    # -- Hindi entity extraction --

    def test_extract_hindi_survey_number(self):
        text = "सर्वे नंबर: 123/5"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.SURVEY_NUMBER)
        assert len(matches) >= 1

    def test_extract_hindi_khasra(self):
        text = "खसरा नं: 78/2"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.KHASRA_NUMBER)
        assert len(matches) >= 1

    # -- Area with unit --

    def test_extract_area_with_unit(self):
        text = "Area: 2.5 hectares"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.AREA)
        assert len(matches) >= 1
        assert matches[0].secondary_value is not None
        assert "hectare" in matches[0].secondary_value.lower()

    def test_extract_area_bigha(self):
        text = "Total area: 10 bigha"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.AREA)
        assert len(matches) >= 1

    # -- Location fields --

    def test_extract_village(self):
        text = "Village: Ramnagar, Tehsil: Sadar"
        result = self.extractor.extract(text)
        villages = result.by_type(EntityType.VILLAGE)
        assert len(villages) >= 1
        assert "Ramnagar" in villages[0].value

    def test_extract_tehsil(self):
        text = "Tehsil: Sadar, District: Lucknow"
        result = self.extractor.extract(text)
        tehsils = result.by_type(EntityType.TEHSIL)
        assert len(tehsils) >= 1

    def test_extract_district(self):
        text = "District: Lucknow, State: Uttar Pradesh"
        result = self.extractor.extract(text)
        districts = result.by_type(EntityType.DISTRICT)
        assert len(districts) >= 1
        assert "Lucknow" in districts[0].value

    # -- Dates --

    def test_extract_date_dd_mm_yyyy(self):
        text = "Date: 15/03/2023"
        result = self.extractor.extract(text)
        dates = result.by_type(EntityType.DATE)
        assert len(dates) >= 1

    def test_extract_date_dd_mon_yyyy(self):
        text = "Registered on 15 Jan 2024"
        result = self.extractor.extract(text)
        dates = result.by_type(EntityType.DATE)
        assert len(dates) >= 1

    # -- Amounts --

    def test_extract_amount_rupee_symbol(self):
        text = "Amount: ₹50,000.00"
        result = self.extractor.extract(text)
        amounts = result.by_type(EntityType.AMOUNT)
        assert len(amounts) >= 1
        assert "50,000.00" in amounts[0].value

    def test_extract_amount_rs(self):
        text = "Rs. 1,00,000"
        result = self.extractor.extract(text)
        amounts = result.by_type(EntityType.AMOUNT)
        assert len(amounts) >= 1

    # -- Person names --

    def test_extract_person_name_owner(self):
        text = "Name of owner: Ramesh Kumar s/o Suresh Kumar"
        result = self.extractor.extract(text)
        persons = result.by_type(EntityType.PERSON)
        assert len(persons) >= 1

    def test_extract_person_buyer(self):
        text = "Buyer: Anil Sharma, Seller: Priya Gupta"
        result = self.extractor.extract(text)
        persons = result.by_type(EntityType.PERSON)
        assert len(persons) >= 2

    # -- Registration / mutation numbers --

    def test_extract_registration_number(self):
        text = "Registration No: 12345/2023"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.REGISTRATION_NUMBER)
        assert len(matches) >= 1

    def test_extract_mutation_number(self):
        text = "Mutation Number: 789"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.MUTATION_NUMBER)
        assert len(matches) >= 1

    # -- Classification / ownership type --

    def test_extract_land_classification(self):
        text = "Land type: agricultural"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.LAND_CLASSIFICATION)
        assert len(matches) >= 1
        assert "agricultural" in matches[0].value.lower()

    def test_extract_ownership_type(self):
        text = "Ownership type: joint"
        result = self.extractor.extract(text)
        matches = result.by_type(EntityType.OWNERSHIP_TYPE)
        assert len(matches) >= 1

    # -- Provenance tracking --

    def test_entity_has_provenance(self):
        text = "Survey No. 999"
        result = self.extractor.extract(text, page_number=3)
        ent = result.by_type(EntityType.SURVEY_NUMBER)[0]
        assert ent.page_number == 3
        assert ent.char_start is not None
        assert ent.char_end is not None
        assert ent.context is not None
        assert ent.extraction_method == "regex"
        assert ent.confidence > 0

    # -- Multi-page & merge --

    def test_multi_page_extraction(self):
        pages = [
            ("Survey No. 100", 1),
            ("District: Lucknow", 2),
        ]
        results = self.extractor.extract_multi_page(pages)
        assert len(results) == 2
        assert results[0].page_number == 1
        assert results[1].page_number == 2

    def test_merge_deduplicates_cross_page(self):
        pages = [
            ("Survey No. 100", 1),
            ("Survey No. 100", 2),
        ]
        results = self.extractor.extract_multi_page(pages)
        merged = self.extractor.merge_results(results)
        survey_ents = merged.by_type(EntityType.SURVEY_NUMBER)
        assert len(survey_ents) == 1  # deduped

    def test_merge_keeps_different_values(self):
        pages = [
            ("Survey No. 100", 1),
            ("Survey No. 200", 2),
        ]
        results = self.extractor.extract_multi_page(pages)
        merged = self.extractor.merge_results(results)
        survey_ents = merged.by_type(EntityType.SURVEY_NUMBER)
        assert len(survey_ents) == 2

    # -- ExtractionResult helpers --

    def test_best_by_type(self):
        text = "Survey No. 100 and Survey No. 200"
        result = self.extractor.extract(text)
        best = result.best_by_type(EntityType.SURVEY_NUMBER)
        assert best is not None

    def test_best_by_type_missing(self):
        result = self.extractor.extract("No entities here.")
        best = result.best_by_type(EntityType.SURVEY_NUMBER)
        assert best is None


# ============================================================================
# 3. FieldNormalizer
# ============================================================================

from app.services.extraction.normalizer import FieldNormalizer


class TestFieldNormalizer:
    """Tests for the field value normalizer."""

    def setup_method(self):
        self.normalizer = FieldNormalizer()

    # -- Text normalization --

    def test_normalize_text_nfc(self):
        result = self.normalizer.normalize_text("  hello   world  ")
        assert result == "hello world"

    def test_normalize_text_empty(self):
        assert self.normalizer.normalize_text("") == ""

    # -- Name normalization --

    def test_normalize_name_title_case(self):
        result = self.normalizer.normalize_name("ramesh kumar")
        assert result == "Ramesh Kumar"

    def test_normalize_name_strip_honorific_shri(self):
        result = self.normalizer.normalize_name("Shri Ramesh Kumar")
        assert result == "Ramesh Kumar"

    def test_normalize_name_strip_honorific_smt(self):
        result = self.normalizer.normalize_name("Smt. Priya Devi")
        assert result == "Priya Devi"

    def test_normalize_name_strip_hindi_honorific(self):
        result = self.normalizer.normalize_name("श्री रामेश्वर")
        assert "रामेश्वर" in result
        assert "श्री" not in result

    def test_normalize_name_empty(self):
        assert self.normalizer.normalize_name("") == ""

    # -- Number normalization --

    def test_normalize_number_simple(self):
        assert self.normalizer.normalize_number("123.45") == 123.45

    def test_normalize_number_commas(self):
        assert self.normalizer.normalize_number("1,00,000") == 100000.0

    def test_normalize_number_devanagari(self):
        result = self.normalizer.normalize_number("१२३")
        assert result == 123.0

    def test_normalize_number_empty(self):
        assert self.normalizer.normalize_number("") is None

    def test_normalize_number_invalid(self):
        assert self.normalizer.normalize_number("abc") is None

    # -- Area unit normalization --

    def test_normalize_area_unit_hectare(self):
        assert self.normalizer.normalize_area_unit("hectares") == "hectare"

    def test_normalize_area_unit_hindi(self):
        assert self.normalizer.normalize_area_unit("हेक्टेयर") == "hectare"
        assert self.normalizer.normalize_area_unit("एकड़") == "acre"
        assert self.normalizer.normalize_area_unit("बीघा") == "bigha"

    def test_normalize_area_unit_sq_meter(self):
        assert self.normalizer.normalize_area_unit("sq meter") == "sq_meter"
        assert self.normalizer.normalize_area_unit("sq ft") == "sq_feet"

    def test_normalize_area_unit_empty(self):
        assert self.normalizer.normalize_area_unit("") == ""

    # -- Date normalization --

    def test_normalize_date_dd_mm_yyyy_slash(self):
        result = self.normalizer.normalize_date("15/03/2023")
        assert result == "2023-03-15"

    def test_normalize_date_dd_mm_yyyy_dash(self):
        result = self.normalizer.normalize_date("15-03-2023")
        assert result == "2023-03-15"

    def test_normalize_date_dd_mm_yyyy_dot(self):
        result = self.normalizer.normalize_date("15.03.2023")
        assert result == "2023-03-15"

    def test_normalize_date_dd_mon_yyyy(self):
        result = self.normalizer.normalize_date("15 Jan 2024")
        assert result == "2024-01-15"

    def test_normalize_date_iso_passthrough(self):
        result = self.normalizer.normalize_date("2023-03-15")
        assert result == "2023-03-15"

    def test_normalize_date_two_digit_year(self):
        result = self.normalizer.normalize_date("15/03/23")
        assert result == "2023-03-15"

    def test_normalize_date_devanagari_digits(self):
        result = self.normalizer.normalize_date("१५/०३/२०२३")
        assert result == "2023-03-15"

    def test_normalize_date_invalid(self):
        assert self.normalizer.normalize_date("not a date") is None

    def test_normalize_date_empty(self):
        assert self.normalizer.normalize_date("") is None

    # -- Survey number normalization --

    def test_normalize_survey_number(self):
        result = self.normalizer.normalize_survey_number("123/4a")
        assert result == "123/4A"

    def test_normalize_survey_number_devanagari(self):
        result = self.normalizer.normalize_survey_number("१२३")
        assert result == "123"

    # -- Classification / ownership normalization --

    def test_normalize_land_classification_english(self):
        assert self.normalizer.normalize_land_classification("Agricultural") == "agricultural"

    def test_normalize_land_classification_hindi(self):
        assert self.normalizer.normalize_land_classification("कृषि") == "agricultural"
        assert self.normalizer.normalize_land_classification("आवासीय") == "residential"

    def test_normalize_ownership_type_english(self):
        assert self.normalizer.normalize_ownership_type("Joint") == "joint"

    def test_normalize_ownership_type_hindi(self):
        assert self.normalizer.normalize_ownership_type("एकल") == "sole"
        assert self.normalizer.normalize_ownership_type("संयुक्त") == "joint"

    # -- Amount normalization --

    def test_normalize_amount(self):
        assert self.normalizer.normalize_amount("50,000.00") == 50000.0


# ============================================================================
# 4. FieldMapper
# ============================================================================

from app.services.extraction.field_mapper import (
    FieldMapper,
    FieldProvenance,
    MappedRecord,
)


class TestFieldMapper:
    """Tests for entity-to-field mapping."""

    def setup_method(self):
        self.mapper = FieldMapper()

    def _make_extraction(self, entities: list[EntitySpan]) -> ExtractionResult:
        return ExtractionResult(
            entities=entities,
            text_length=100,
            entity_count=len(entities),
        )

    # -- Basic mapping --

    def test_map_survey_number(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.SURVEY_NUMBER,
                value="123/4",
                raw_text="Survey No. 123/4",
                confidence=0.85,
                extraction_method="regex",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert "survey_number" in result.fields
        assert result.fields["survey_number"] == "123/4"  # normalized (uppercased, no whitespace)

    def test_map_village_normalized(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.VILLAGE,
                value="ramnagar",
                raw_text="Village: ramnagar",
                confidence=0.75,
                extraction_method="regex",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert result.fields["village"] == "Ramnagar"

    # -- Conflict resolution (highest confidence wins) --

    def test_conflict_resolution_highest_confidence(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.DISTRICT,
                value="Lucknow",
                raw_text="District: Lucknow",
                confidence=0.75,
                extraction_method="regex",
            ),
            EntitySpan(
                entity_type=EntityType.DISTRICT,
                value="Kanpur",
                raw_text="District: Kanpur",
                confidence=0.90,
                extraction_method="regex",
            ),
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert result.fields["district"] == "Kanpur"

    # -- Area + unit compound --

    def test_area_with_secondary_unit(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.AREA,
                value="2.5",
                raw_text="Area: 2.5 hectares",
                confidence=0.80,
                extraction_method="regex",
                secondary_value="hectares",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert result.fields["area"] == 2.5
        assert result.fields["area_unit"] == "hectare"

    # -- Person mapping --

    def test_person_mapping(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.PERSON,
                value="Shri Ramesh Kumar",
                raw_text="Owner: Shri Ramesh Kumar",
                confidence=0.70,
                extraction_method="regex",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert len(result.persons) == 1
        assert result.persons[0]["name"] == "Ramesh Kumar"

    # -- Date mapping with context --

    def test_date_maps_to_mutation_date(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.DATE,
                value="15/03/2023",
                raw_text="Date: 15/03/2023",
                confidence=0.70,
                extraction_method="regex",
                context="mutation order dated 15/03/2023 dakhil kharij",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert "mutation_date" in result.fields
        assert result.fields["mutation_date"] == "2023-03-15"

    def test_date_maps_to_registration_date(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.DATE,
                value="20/06/2022",
                raw_text="Date: 20/06/2022",
                confidence=0.70,
                extraction_method="regex",
                context="registration office registered on 20/06/2022",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert "registration_date" in result.fields

    # -- Amount mapping with context --

    def test_amount_maps_to_stamp_duty(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.AMOUNT,
                value="5000",
                raw_text="₹5,000",
                confidence=0.75,
                extraction_method="regex",
                context="stamp duty of ₹5,000 paid",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert "stamp_duty" in result.fields

    def test_amount_maps_to_consideration(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.AMOUNT,
                value="500000",
                raw_text="₹5,00,000",
                confidence=0.75,
                extraction_method="regex",
                context="consideration amount of ₹5,00,000",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert "consideration_amount" in result.fields

    # -- Provenance tracking --

    def test_provenance_tracked(self):
        entities = [
            EntitySpan(
                entity_type=EntityType.SURVEY_NUMBER,
                value="999",
                raw_text="Survey No. 999",
                confidence=0.85,
                extraction_method="regex",
                page_number=2,
                char_start=10,
                char_end=13,
                context="Survey No. 999 in village",
            )
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert len(result.provenance) >= 1
        prov = result.provenance[0]
        assert prov.field_name == "survey_number"
        assert prov.raw_value == "999"
        assert prov.confidence == 0.85
        assert prov.page_number == 2

    # -- Field count --

    def test_field_count(self):
        entities = [
            EntitySpan(entity_type=EntityType.SURVEY_NUMBER, value="100", raw_text="", confidence=0.8, extraction_method="regex"),
            EntitySpan(entity_type=EntityType.VILLAGE, value="Test", raw_text="", confidence=0.7, extraction_method="regex"),
            EntitySpan(entity_type=EntityType.DISTRICT, value="Dist", raw_text="", confidence=0.7, extraction_method="regex"),
        ]
        result = self.mapper.map_entities(self._make_extraction(entities))
        assert result.field_count >= 3

    # -- Document type passthrough --

    def test_document_type_set(self):
        result = self.mapper.map_entities(
            self._make_extraction([]),
            document_type="sale_deed",
        )
        assert result.fields.get("document_type") == "sale_deed"


# ============================================================================
# 5. ConfidenceEngine
# ============================================================================

from app.services.confidence.engine import (
    ConfidenceBreakdown,
    ConfidenceEngine,
    FieldConfidence,
)


class TestConfidenceEngine:
    """Tests for the composite confidence scorer."""

    def setup_method(self):
        self.engine = ConfidenceEngine()

    def test_empty_record(self):
        result = self.engine.score({})
        assert result.overall == 0.0
        assert result.field_count == 0

    def test_single_field_scoring(self):
        fields = {"survey_number": "123/4A"}
        provenance = [
            {"field_name": "survey_number", "confidence": 0.85, "extraction_method": "regex", "context": "Survey No. 123/4A"},
        ]
        result = self.engine.score(fields, ocr_confidence=0.9, provenance=provenance)
        assert result.field_count == 1
        assert result.overall > 0
        fc = result.field_scores["survey_number"]
        assert fc.ocr_confidence == 0.9
        assert fc.extraction_confidence == 0.85
        assert fc.composite > 0

    def test_pattern_score_full_match(self):
        fields = {"survey_number": "123/4A"}
        result = self.engine.score(fields, ocr_confidence=0.8)
        fc = result.field_scores["survey_number"]
        assert fc.pattern_confidence == 1.0

    def test_pattern_score_no_pattern(self):
        fields = {"village": "Ramnagar"}
        result = self.engine.score(fields, ocr_confidence=0.8)
        fc = result.field_scores["village"]
        assert fc.pattern_confidence == 0.7  # default for no-pattern fields

    def test_cross_field_score_related_present(self):
        fields = {"survey_number": "100", "village": "Ramnagar"}
        result = self.engine.score(fields, ocr_confidence=0.8)
        # survey_number has village as related field (present) → score > 0
        fc = result.field_scores["survey_number"]
        assert fc.cross_field_confidence > 0

    def test_cross_field_score_related_missing(self):
        fields = {"survey_number": "100"}
        result = self.engine.score(fields, ocr_confidence=0.8)
        fc = result.field_scores["survey_number"]
        assert fc.cross_field_confidence == 0.0  # village not present

    def test_context_score_with_keywords(self):
        fields = {"survey_number": "100"}
        provenance = [
            {"field_name": "survey_number", "confidence": 0.8, "extraction_method": "regex", "context": "Survey number 100 in village"},
        ]
        result = self.engine.score(fields, ocr_confidence=0.8, provenance=provenance)
        fc = result.field_scores["survey_number"]
        assert fc.context_confidence > 0.5

    def test_low_confidence_flagging(self):
        fields = {"survey_number": "???"}
        result = self.engine.score(fields, ocr_confidence=0.1)
        if result.field_scores["survey_number"].composite < 0.5:
            assert "survey_number" in result.low_confidence_fields

    def test_multiple_fields_overall(self):
        fields = {
            "survey_number": "100",
            "village": "Ramnagar",
            "district": "Lucknow",
        }
        result = self.engine.score(fields, ocr_confidence=0.8)
        assert result.field_count == 3
        assert result.overall > 0

    def test_none_values_skipped(self):
        fields = {"survey_number": "100", "village": None}
        result = self.engine.score(fields, ocr_confidence=0.8)
        assert result.field_count == 1

    def test_to_dict(self):
        fields = {"survey_number": "100"}
        result = self.engine.score(fields, ocr_confidence=0.8)
        d = result.to_dict()
        assert "overall" in d
        assert "fields" in d
        assert "survey_number" in d["fields"]


# ============================================================================
# 6. ValidationEngine
# ============================================================================

from app.services.validation import (
    ValidationEngine,
    ValidationIssue,
    ValidationResult,
    ValidationStatus,
    RuleType,
)


class TestValidationEngine:
    """Tests for the deterministic validation engine."""

    def setup_method(self):
        self.engine = ValidationEngine()

    # -- Required fields --

    def test_required_fields_present(self):
        record = {"survey_number": "100", "village": "Ramnagar", "district": "Lucknow"}
        result = self.engine.validate(record)
        req_issues = [i for i in result.issues if i.rule_name == "required_field"]
        passed = [i for i in req_issues if i.status == ValidationStatus.PASSED]
        assert len(passed) == 3

    def test_required_fields_missing(self):
        record = {}
        result = self.engine.validate(record)
        req_issues = [i for i in result.issues if i.rule_name == "required_field"]
        failed = [i for i in req_issues if i.status == ValidationStatus.FAILED]
        assert len(failed) == 3

    def test_required_field_empty_string(self):
        record = {"survey_number": "", "village": "X", "district": "Y"}
        result = self.engine.validate(record)
        failed = [i for i in result.issues if i.rule_name == "required_field" and i.status == ValidationStatus.FAILED]
        assert len(failed) == 1
        assert failed[0].field_name == "survey_number"

    # -- Area validation --

    def test_area_positive(self):
        record = {"survey_number": "1", "village": "V", "district": "D", "area": -5}
        result = self.engine.validate(record)
        area_issues = [i for i in result.issues if i.field_name == "area" and i.status == ValidationStatus.FAILED]
        assert len(area_issues) >= 1

    def test_area_within_range(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "area": 5.0, "area_unit": "hectare",
        }
        result = self.engine.validate(record)
        range_issues = [i for i in result.issues if i.rule_name == "area_range" and i.status == ValidationStatus.PASSED]
        assert len(range_issues) >= 1

    def test_area_exceeds_max(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "area": 999999, "area_unit": "hectare",
        }
        result = self.engine.validate(record)
        warnings = [i for i in result.issues if i.rule_name == "area_range" and i.status == ValidationStatus.WARNING]
        assert len(warnings) >= 1

    def test_area_without_unit(self):
        record = {"survey_number": "1", "village": "V", "district": "D", "area": 10}
        result = self.engine.validate(record)
        review = [i for i in result.issues if i.rule_name == "area_unit_present"]
        assert len(review) == 1
        assert review[0].status == ValidationStatus.REVIEW_REQUIRED

    # -- Survey number format --

    def test_survey_number_unusual_chars(self):
        record = {"survey_number": "123@#$", "village": "V", "district": "D"}
        result = self.engine.validate(record)
        fmt_issues = [i for i in result.issues if i.rule_name == "survey_number_format"]
        assert len(fmt_issues) >= 1

    def test_survey_number_too_long(self):
        record = {"survey_number": "A" * 60, "village": "V", "district": "D"}
        result = self.engine.validate(record)
        len_issues = [i for i in result.issues if i.rule_name == "survey_number_length"]
        assert len(len_issues) >= 1

    # -- Date validation --

    def test_valid_date(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "mutation_date": "2023-01-15",
        }
        result = self.engine.validate(record)
        date_issues = [i for i in result.issues if i.rule_name == "mutation_date_valid"]
        assert len(date_issues) == 1
        assert date_issues[0].status == ValidationStatus.PASSED

    def test_future_date_fails(self):
        future = (date.today() + timedelta(days=365)).isoformat()
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "mutation_date": future,
        }
        result = self.engine.validate(record)
        failed = [i for i in result.issues if "future" in i.rule_name]
        assert len(failed) >= 1
        assert failed[0].status == ValidationStatus.FAILED

    def test_very_old_date_needs_review(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "mutation_date": "1750-06-01",
        }
        result = self.engine.validate(record)
        old = [i for i in result.issues if "too_old" in i.rule_name]
        assert len(old) >= 1
        assert old[0].status == ValidationStatus.REVIEW_REQUIRED

    # -- Ownership percentage --

    def test_ownership_percentage_out_of_range(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "ownership_percentage": 150,
        }
        result = self.engine.validate(record)
        pct = [i for i in result.issues if i.rule_name == "ownership_pct_range"]
        assert len(pct) >= 1
        assert pct[0].status == ValidationStatus.FAILED

    def test_multi_owner_pct_sum_mismatch(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "owners": [
                {"name": "A", "ownership_percentage": 40},
                {"name": "B", "ownership_percentage": 40},
            ],
        }
        result = self.engine.validate(record)
        sum_issues = [i for i in result.issues if i.rule_name == "ownership_pct_sum"]
        assert len(sum_issues) >= 1

    # -- Enum validation --

    def test_valid_land_classification(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "land_classification": "agricultural",
        }
        result = self.engine.validate(record)
        lc_issues = [i for i in result.issues if i.rule_name == "land_classification_valid"]
        assert len(lc_issues) == 0

    def test_invalid_land_classification(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "land_classification": "martian",
        }
        result = self.engine.validate(record)
        lc_issues = [i for i in result.issues if i.rule_name == "land_classification_valid"]
        assert len(lc_issues) >= 1
        assert lc_issues[0].status == ValidationStatus.WARNING

    # -- Location hierarchy --

    def test_village_without_district_warns(self):
        record = {"survey_number": "1", "village": "V"}
        result = self.engine.validate(record)
        loc = [i for i in result.issues if i.rule_name == "location_hierarchy"]
        assert len(loc) >= 1

    def test_unrecognized_state(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "state": "Narnia",
        }
        result = self.engine.validate(record)
        state_issues = [i for i in result.issues if i.rule_name == "state_valid"]
        assert len(state_issues) >= 1
        assert state_issues[0].status == ValidationStatus.REVIEW_REQUIRED

    def test_recognized_state_no_issue(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "state": "Uttar Pradesh",
        }
        result = self.engine.validate(record)
        state_issues = [i for i in result.issues if i.rule_name == "state_valid"]
        assert len(state_issues) == 0

    def test_duplicate_location_names(self):
        record = {
            "survey_number": "1", "village": "Lucknow",
            "district": "Lucknow",
        }
        result = self.engine.validate(record)
        dup = [i for i in result.issues if i.rule_name == "location_duplicates"]
        assert len(dup) >= 1

    # -- Person field validation --

    def test_short_person_name(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "persons": [{"name": "A"}],
        }
        result = self.engine.validate(record)
        name_issues = [i for i in result.issues if i.rule_name == "person_name_length"]
        assert len(name_issues) >= 1

    # -- Amount validation --

    def test_negative_amount_fails(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "consideration_amount": -1000,
        }
        result = self.engine.validate(record)
        amt = [i for i in result.issues if "positive" in i.rule_name]
        assert len(amt) >= 1
        assert amt[0].status == ValidationStatus.FAILED

    def test_stamp_exceeds_consideration(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "consideration_amount": 100000,
            "stamp_duty": 200000,
        }
        result = self.engine.validate(record)
        cross = [i for i in result.issues if i.rule_name == "stamp_vs_consideration"]
        assert len(cross) >= 1

    # -- Confidence thresholds --

    def test_low_confidence_flagged(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "field_confidences": {"survey_number": {"composite": 0.3}},
        }
        result = self.engine.validate(record)
        conf = [i for i in result.issues if i.rule_name == "low_confidence"]
        assert len(conf) >= 1
        assert conf[0].status == ValidationStatus.REVIEW_REQUIRED

    def test_moderate_confidence_warned(self):
        record = {
            "survey_number": "1", "village": "V", "district": "D",
            "field_confidences": {"survey_number": {"composite": 0.55}},
        }
        result = self.engine.validate(record)
        conf = [i for i in result.issues if i.rule_name == "moderate_confidence"]
        assert len(conf) >= 1
        assert conf[0].status == ValidationStatus.WARNING

    # -- Overall status computation --

    def test_status_passed(self):
        record = {"survey_number": "100", "village": "V", "district": "D"}
        result = self.engine.validate(record)
        # No failures → status should be passed or warning depending on other checks
        assert result.status in ("passed", "warning", "review_required")

    def test_status_failed_on_failure(self):
        record = {"survey_number": "100", "village": "V", "district": "D", "area": -1}
        result = self.engine.validate(record)
        assert result.status == ValidationStatus.FAILED
        assert not result.is_valid

    def test_status_review_required(self):
        record = {"survey_number": "1", "village": "V", "district": "D", "area": 10}
        # area without unit triggers review_required
        result = self.engine.validate(record)
        assert result.needs_review


# ============================================================================
# 7. ExtractionPipeline (integration)
# ============================================================================

from app.services.extraction.extraction_pipeline import (
    ExtractionPipeline,
    ExtractionPipelineResult,
)


class TestExtractionPipeline:
    """Integration tests for the full extraction pipeline."""

    def setup_method(self):
        self.pipeline = ExtractionPipeline()

    def test_empty_text(self):
        result = self.pipeline.extract("")
        # Classification should return miscellaneous
        assert result.classification is not None
        assert result.classification.category == DocumentCategory.MISCELLANEOUS
        assert result.processing_time_ms >= 0

    def test_full_pipeline_sale_deed(self):
        text = """
        SALE DEED

        This deed of sale is executed between:
        Buyer: Ramesh Kumar s/o Suresh Kumar
        Seller: Priya Devi w/o Mohan Lal

        Survey No. 123/4A
        Village: Ramnagar, Tehsil: Sadar, District: Lucknow, State: Uttar Pradesh
        Area: 2.5 hectares
        Land type: agricultural

        Consideration amount: Rs. 50,00,000
        Stamp duty: Rs. 3,50,000
        Registration No: 5678/2023
        Date: 15/03/2023

        Witness 1: Anil Singh
        Witness 2: Vikram Sharma
        """
        result = self.pipeline.extract(
            text,
            page_texts=[text],
            page_count=1,
            ocr_confidence=0.85,
        )

        # Classification
        assert result.classification is not None
        assert result.classification.category == DocumentCategory.SALE_DEED

        # Extraction
        assert result.extraction is not None
        assert result.extraction.entity_count > 0

        # Mapped record
        assert result.mapped_record is not None
        assert result.mapped_record.field_count > 0
        assert "survey_number" in result.mapped_record.fields
        assert "village" in result.mapped_record.fields
        assert len(result.mapped_record.persons) >= 1

        # Confidence
        assert result.confidence is not None
        assert result.confidence.overall > 0

        # Validation
        assert result.validation is not None
        assert result.validation.status in ("passed", "warning", "review_required", "failed")

        # Processing time recorded
        assert result.processing_time_ms >= 0

    def test_pipeline_with_errors_continues(self):
        # Even if text is unusual, pipeline should not crash
        result = self.pipeline.extract(
            "Some random text with no land records.",
            page_count=1,
            ocr_confidence=0.5,
        )
        assert result is not None
        assert result.classification is not None

    def test_pipeline_multi_page(self):
        page1 = "Survey No. 100, Village: TestVillage"
        page2 = "District: TestDistrict, State: Rajasthan"
        result = self.pipeline.extract(
            full_text=page1 + "\n" + page2,
            page_texts=[page1, page2],
            page_count=2,
            ocr_confidence=0.9,
        )
        assert result.extraction is not None
        assert result.mapped_record is not None

    def test_pipeline_hindi_document(self):
        text = """
        अधिकार अभिलेख
        सर्वे नंबर: ४५६/२
        ग्राम: रामपुर, तहसील: सदर, जिला: लखनऊ
        क्षेत्रफल: ३.५ हेक्टेयर
        भूमि प्रकार: कृषि
        मालिक का नाम: श्री रामेश्वर प्रसाद
        """
        result = self.pipeline.extract(text, page_count=1, ocr_confidence=0.7)
        assert result.classification is not None
        assert result.extraction is not None
        assert result.extraction.entity_count > 0
