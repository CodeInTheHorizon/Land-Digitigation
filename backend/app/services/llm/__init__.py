"""LLM abstraction layer – provider-agnostic interface for AI reasoning."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMService(ABC):
    """Abstract LLM interface."""

    @abstractmethod
    async def extract_fields(
        self,
        text: str,
        document_type: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract structured land-record fields from text using LLM reasoning."""
        ...

    @abstractmethod
    async def validate_record(
        self,
        record: Dict[str, Any],
        text: str,
    ) -> Dict[str, Any]:
        """Use LLM to validate extracted fields against source text."""
        ...

    @abstractmethod
    async def classify_document(self, text: str) -> Dict[str, Any]:
        """Classify the type of land document."""
        ...


class OpenAILLMService(LLMService):
    """OpenAI GPT-based implementation."""

    def __init__(self) -> None:
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    async def _chat(self, system: str, user: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        return response.choices[0].message.content or ""

    async def extract_fields(
        self,
        text: str,
        document_type: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        system = """You are an expert in Indian land records. Extract structured fields from the given text.
Return a JSON object with these fields (use null for missing):
{
  "landowner_name": str, "father_husband_name": str, "guardian_name": str,
  "survey_number": str, "khasra_number": str, "khata_number": str, "plot_number": str,
  "area": number, "area_unit": str,
  "village": str, "tehsil": str, "district": str, "state": str,
  "land_classification": str, "ownership_type": str, "ownership_percentage": number,
  "mutation_number": str, "mutation_type": str, "mutation_date": str,
  "registration_number": str, "registration_date": str, "transaction_type": str,
  "document_type": str, "document_number": str, "remarks": str
}
Return ONLY valid JSON."""

        user_msg = f"Document type: {document_type or 'unknown'}\nLanguage: {language or 'unknown'}\n\nText:\n{text[:4000]}"
        raw = await self._chat(system, user_msg)

        import json
        try:
            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("llm.extract_parse_failed", raw_response=raw[:200])
            return {}

    async def validate_record(self, record: Dict[str, Any], text: str) -> Dict[str, Any]:
        system = """You are a land record validation expert. Compare the extracted record against the source text.
For each field, assess:
- is_correct: bool
- confidence: 0.0-1.0
- suggested_value: str or null (if the field needs correction)
- reason: str
Return a JSON object mapping field names to these assessments."""

        user_msg = f"Extracted record:\n{record}\n\nSource text:\n{text[:4000]}"
        raw = await self._chat(system, user_msg)

        import json
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {}

    async def classify_document(self, text: str) -> Dict[str, Any]:
        system = """Classify this Indian land document. Return JSON:
{
  "document_type": one of ["khasra", "khatauni", "jamabandi", "mutation_order", "sale_deed", "registry", "map", "revenue_record", "court_order", "other"],
  "confidence": 0.0-1.0,
  "language": ISO-639 code,
  "description": brief description
}"""
        raw = await self._chat(system, f"Text:\n{text[:3000]}")

        import json
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"document_type": "other", "confidence": 0.0}


class AnthropicLLMService(LLMService):
    """Anthropic Claude-based implementation."""

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL

    async def _chat(self, system: str, user: str) -> str:
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text if message.content else ""

    async def extract_fields(self, text, document_type=None, language=None):
        # Same prompts as OpenAI version
        return await OpenAILLMService.extract_fields(self, text, document_type, language)

    async def validate_record(self, record, text):
        return await OpenAILLMService.validate_record(self, record, text)

    async def classify_document(self, text):
        return await OpenAILLMService.classify_document(self, text)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_llm_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_instance
    if _llm_instance is None:
        if settings.LLM_PROVIDER == "anthropic":
            _llm_instance = AnthropicLLMService()
        else:
            _llm_instance = OpenAILLMService()
    return _llm_instance
