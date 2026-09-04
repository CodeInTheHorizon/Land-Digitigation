"""Tests for NLP entity extraction."""

import pytest

from app.services.nlp import LandRecordEntityExtractor


@pytest.fixture
def extractor():
    return LandRecordEntityExtractor()


class TestEntityExtraction:
    def test_survey_number(self, extractor):
        text = "Survey No: 123/4A is located in the village."
        fields = extractor.extract(text)
        survey = [f for f in fields if f.field_name == "survey_number"]
        assert len(survey) >= 1
        assert "123/4A" in survey[0].value

    def test_khasra_number(self, extractor):
        text = "Khasra Number: 456/7 dated 2020"
        fields = extractor.extract(text)
        khasra = [f for f in fields if f.field_name == "khasra_number"]
        assert len(khasra) >= 1
        assert "456/7" in khasra[0].value

    def test_hindi_survey(self, extractor):
        text = "सर्वे नंबर: 789 ग्राम में स्थित है"
        fields = extractor.extract(text)
        survey = [f for f in fields if f.field_name == "survey_number"]
        assert len(survey) >= 1

    def test_district(self, extractor):
        text = "District: Pune is in Maharashtra"
        fields = extractor.extract(text)
        district = [f for f in fields if f.field_name == "district"]
        assert len(district) >= 1
        assert "Pune" in district[0].value

    def test_no_fields(self, extractor):
        text = "This is a random document with no land record fields."
        fields = extractor.extract(text)
        assert len(fields) == 0
