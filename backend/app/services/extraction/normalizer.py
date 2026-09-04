"""Field value normalization for Indian land records.

Handles:
  - Date normalization (multiple formats → ISO 8601)
  - Area/unit normalization (Hindi unit names → canonical English)
  - Name normalization (Unicode NFC, title case, whitespace cleanup)
  - Number normalization (commas, Devanagari digits)
  - Survey/khasra number cleanup

Pure functions — no state, no I/O.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Optional, Tuple


class FieldNormalizer:
    """Normalize extracted field values into canonical form."""

    # Devanagari digit → ASCII digit
    _DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

    # Hindi/regional area unit → canonical English
    _AREA_UNIT_MAP = {
        # Hindi
        "हेक्टेयर": "hectare",
        "एकड़": "acre",
        "बीघा": "bigha",
        "वर्ग मी": "sq_meter",
        "वर्ग मीटर": "sq_meter",
        "गुंठा": "guntha",
        "कनाल": "kanal",
        "मरला": "marla",
        # English variants
        "hectare": "hectare",
        "hectares": "hectare",
        "hect": "hectare",
        "acre": "acre",
        "acres": "acre",
        "bigha": "bigha",
        "sq m": "sq_meter",
        "sq meter": "sq_meter",
        "sq metre": "sq_meter",
        "sq meters": "sq_meter",
        "sq ft": "sq_feet",
        "sq feet": "sq_feet",
        "sq foot": "sq_feet",
        "guntha": "guntha",
        "kanal": "kanal",
        "marla": "marla",
        "dismil": "dismil",
    }

    # Land classification normalization
    _CLASSIFICATION_MAP = {
        "कृषि": "agricultural",
        "आवासीय": "residential",
        "वाणिज्यिक": "commercial",
        "औद्योगिक": "industrial",
        "बंजर": "barren",
        "वन": "forest",
        "सरकारी": "govt",
        "agricultural": "agricultural",
        "residential": "residential",
        "commercial": "commercial",
        "industrial": "industrial",
        "barren": "barren",
        "forest": "forest",
        "govt": "govt",
        "government": "govt",
        "wetland": "wetland",
        "pasture": "pasture",
    }

    # Ownership type normalization
    _OWNERSHIP_MAP = {
        "एकल": "sole",
        "संयुक्त": "joint",
        "विरासत": "inherited",
        "पट्टा": "leased",
        "सरकारी": "government",
        "sole": "sole",
        "joint": "joint",
        "inherited": "inherited",
        "leased": "leased",
        "government": "government",
    }

    def normalize_text(self, value: str) -> str:
        """General text normalization: NFC, strip, collapse whitespace."""
        if not value:
            return ""
        # Unicode NFC normalization
        normalized = unicodedata.normalize("NFC", value)
        # Collapse whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def normalize_name(self, name: str) -> str:
        """Normalize a person or place name.

        - NFC normalization
        - Title case (for Latin script)
        - Strip honorifics and noise
        - Collapse whitespace
        """
        if not name:
            return ""
        name = self.normalize_text(name)

        # Remove common honorifics/prefixes
        name = re.sub(
            r"^(shri|smt|mr|mrs|ms|dr|श्री|श्रीमती|सुश्री)\.?\s+",
            "", name, flags=re.IGNORECASE,
        )

        # Title case only if mostly Latin
        latin_chars = sum(1 for c in name if c.isascii() and c.isalpha())
        total_alpha = sum(1 for c in name if c.isalpha())
        if total_alpha > 0 and latin_chars / total_alpha > 0.5:
            name = name.title()

        return name.strip()

    def normalize_number(self, value: str) -> Optional[float]:
        """Parse a number that may contain commas or Devanagari digits."""
        if not value:
            return None
        # Translate Devanagari digits
        cleaned = value.translate(self._DEVANAGARI_DIGITS)
        # Remove commas and spaces
        cleaned = cleaned.replace(",", "").replace(" ", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def normalize_area_unit(self, unit: str) -> str:
        """Normalize an area unit to canonical form."""
        if not unit:
            return ""
        key = re.sub(r"\s+", " ", unit.strip().lower())
        # Remove trailing 's' for plurals
        key_singular = key.rstrip("s") if key.endswith("s") and key not in self._AREA_UNIT_MAP else key
        return self._AREA_UNIT_MAP.get(key, self._AREA_UNIT_MAP.get(key_singular, unit.lower()))

    def normalize_date(self, value: str) -> Optional[str]:
        """Parse various date formats into ISO 8601 (YYYY-MM-DD).

        Supported formats:
          - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
          - DD Mon YYYY (e.g., 15 Jan 2024)
          - YYYY-MM-DD (already ISO)
          - Devanagari digits
        """
        if not value:
            return None

        # Translate Devanagari digits first
        cleaned = value.translate(self._DEVANAGARI_DIGITS).strip()

        # Try ISO format first
        if re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
            try:
                datetime.strptime(cleaned, "%Y-%m-%d")
                return cleaned
            except ValueError:
                pass

        # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
        m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})$", cleaned)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if year < 100:
                year += 2000 if year < 50 else 1900
            try:
                d = date(year, month, day)
                return d.isoformat()
            except ValueError:
                # Maybe MM/DD/YYYY? Try swapping
                try:
                    d = date(year, day, month)
                    return d.isoformat()
                except ValueError:
                    pass

        # DD Mon YYYY
        for fmt in ("%d %b %Y", "%d %B %Y", "%d-%b-%Y"):
            try:
                d = datetime.strptime(cleaned, fmt).date()
                return d.isoformat()
            except ValueError:
                continue

        return None

    def normalize_survey_number(self, value: str) -> str:
        """Clean up survey/khasra/khata numbers."""
        if not value:
            return ""
        # Translate Devanagari digits
        cleaned = value.translate(self._DEVANAGARI_DIGITS)
        # Remove extra whitespace
        cleaned = re.sub(r"\s+", "", cleaned).strip()
        # Uppercase any letters
        return cleaned.upper()

    def normalize_amount(self, value: str) -> Optional[float]:
        """Parse monetary amounts."""
        return self.normalize_number(value)

    def normalize_land_classification(self, value: str) -> str:
        """Normalize land classification to canonical form."""
        if not value:
            return ""
        return self._CLASSIFICATION_MAP.get(value.strip().lower(), value.strip().lower())

    def normalize_ownership_type(self, value: str) -> str:
        """Normalize ownership type to canonical form."""
        if not value:
            return ""
        return self._OWNERSHIP_MAP.get(value.strip().lower(), value.strip().lower())
