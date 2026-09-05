"""Conservative labeled-field parsing and a stable, nullable result shape."""

from __future__ import annotations

import re
import unicodedata

from app.services.extraction.normalizer import FieldNormalizer
from app.services.extraction.field_mapper import FieldProvenance

ALIASES = {
    "name": ["owner name", "name of owner", "owner", "खातेदार का नाम", "भूमिस्वामी का नाम", "खातेदार", "भूमिस्वामी", "मालिक का नाम", "स्वामी", "नाम"],
    "father_or_husband_name": ["father or husband name", "father/husband name", "father name", "father", "husband name", "s/o", "d/o", "w/o", "पिता/पति का नाम", "पिता का नाम", "पति का नाम", "पुत्र", "पुत्री", "पत्नी"],
    "address": ["address", "resident of", "r/o", "पता", "निवासी"],
    "survey_number": ["survey number", "survey no", "survey", "सर्वे नंबर", "सर्वे संख्या", "सर्वे नं", "सर्वे"],
    "khasra_number": ["khasra number", "khasra no", "khasra", "खसरा संख्या", "खसरा नंबर", "खसरा नं", "खसरा"],
    "khata_number": ["khata number", "khata no", "khata", "खाता संख्या", "खाता नंबर", "खाता नं", "खाता"],
    "plot_number": ["plot number", "plot no", "plot", "भूखंड संख्या", "भूखंड"],
    "area": ["total area", "area", "रकबा", "क्षेत्रफल"],
    "area_unit": ["area unit", "unit", "इकाई"],
    "village": ["village", "gram", "ग्राम", "गांव", "गाँव", "मौजा"],
    "tehsil": ["tehsil", "tahsil", "taluka", "taluk", "तहसील", "तालुका"],
    "district": ["district", "dist", "जिला", "ज़िला", "जनपद"],
    "state": ["state", "राज्य"],
    "land_classification": ["land classification", "land type", "land use", "भूमि प्रकार", "भूमि वर्गीकरण"],
    "ownership_type": ["ownership type", "स्वामित्व प्रकार"],
    "mutation_number": ["mutation number", "mutation no", "नामांतरण संख्या", "नामांतरण नं"],
    "mutation_date": ["mutation date", "नामांतरण दिनांक", "नामांतरण तिथि"],
    "registration_number": ["registration number", "registration no", "पंजीकरण संख्या", "पंजीकरण नं"],
    "registration_date": ["registration date", "पंजीकरण दिनांक", "पंजीकरण तिथि"],
    "registration_office": ["registration office", "पंजीकरण कार्यालय"],
    "document_number": ["document number", "document no", "दस्तावेज संख्या"],
}


def label_key(text):
    return "".join(c.casefold() for c in unicodedata.normalize("NFC", text) if c.isalpha() or unicodedata.category(c).startswith("M"))


LOOKUP = {label_key(alias): field for field, aliases in ALIASES.items() for alias in aliases}
# Optional horizontal spacing tolerates OCR-separated label letters, without
# joining unrelated lines or fuzzy-matching survey numbers to khata numbers.
LABEL = "|".join("[ \\t]*".join(re.escape(c) for c in alias) for alias in sorted(
    [a for values in ALIASES.values() for a in values], key=len, reverse=True))
LABEL_RE = re.compile(r"(?<!\w)(?P<label>" + LABEL + r")[.]*[ \t]*(?P<separator>[:：=|]|[ \t])", re.IGNORECASE)


def labeled_values(text):
    lines = unicodedata.normalize("NFC", text).replace("\r\n", "\n").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        cells = re.split(r"\s*\|\s*|\t+| {2,}", line)
        if len(cells) > 1 and all(label_key(c) in LOOKUP for c in cells):
            index += 1
            while index < len(lines):
                values = re.split(r"\s*\|\s*|\t+| {2,}", lines[index].strip())
                if len(values) != len(cells) or any(label_key(v) in LOOKUP for v in values):
                    break
                yield from zip(cells, values)
                index += 1
            continue
        if label_key(line.rstrip(":：=")) in LOOKUP:
            if index + 1 < len(lines) and lines[index + 1].strip() and not LABEL_RE.search(lines[index + 1]) and label_key(lines[index + 1]) not in LOOKUP:
                yield line.rstrip(":：="), lines[index + 1].strip()
                index += 2
                continue
        matches = [m for m in LABEL_RE.finditer(line) if m.start() == 0 or m.group("separator") in ":：=|" or LOOKUP[label_key(m.group("label"))] in ("father_or_husband_name", "address")]
        first_pair = re.match(r"([^:：=|]{1,60})[:：=]", line)
        if first_pair and label_key(first_pair.group(1)) not in LOOKUP:
            # "Village code" is an unknown label, not the village's name.
            matches = [m for m in matches if m.start() >= first_pair.end()]
        if matches:
            prefix = line[:matches[0].start()].strip(" ;|")
            unknown = re.match(r"([^:：=]{1,60})[:：=]\s*(.*)", prefix)
            if unknown:
                yield unknown.group(1).strip(), unknown.group(2).strip()
            for i, match in enumerate(matches):
                end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
                # A new, unknown explicit label is a boundary too.
                value = line[match.end():end]
                parts = re.split(r"[;|]\s*(?=[^:：=]{1,60}[:：=])", value, maxsplit=1)
                yield match.group("label"), parts[0].strip(" ,;|")
                if len(parts) == 2:
                    unknown = re.match(r"([^:：=]{1,60})[:：=]\s*(.*)", parts[1])
                    if unknown:
                        yield unknown.group(1).strip(), unknown.group(2).strip()
        else:
            match = re.match(r"([^:：=|]{1,60})\s*[:：=]\s*(.*)", line)
            if match:
                yield match.group(1).strip(), match.group(2).strip()
        index += 1


def clean_value(value):
    value = re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()
    if value.casefold() in {"", "-", "—", "n/a", "na", "null", "unknown", "अज्ञात"}:
        return None
    if not any(c.isalnum() for c in value):
        return None
    return value


def enrich_record(record, text):
    """Prefer explicitly labeled values; keep conflicts for human review."""
    normalizer = FieldNormalizer()
    additional, warnings, observed, owners = {}, [], {}, []
    current_owner = None
    for label, raw in labeled_values(text):
        value = clean_value(raw)
        key = LOOKUP.get(label_key(label))
        if not key:
            if value is not None:
                additional.setdefault(label, [])
                if value not in additional[label]:
                    additional[label].append(value)
            continue
        if key in ("name", "father_or_husband_name", "address"):
            if value and key != "address" and (any(c.isdigit() for c in value) or sum(c.isalpha() for c in value) < 2
                    or any(not (c.isalpha() or unicodedata.category(c).startswith("M") or c in " .'-") for c in value)):
                warnings.append(f"Uncertain {key}; check the original text.")
                value = None
            if key == "name":
                current_owner = {"name": value, "father_or_husband_name": None, "address": None, "confidence": 0.8}
                owners.append(current_owner)
            elif current_owner is not None:
                current_owner[key] = value
            elif value:
                additional.setdefault(label, []).append(value)
            continue
        normalized = value
        if value and key.endswith("_number"):
            normalized = normalizer.normalize_survey_number(value)
            if not re.fullmatch(r"[\w/\-]+", normalized) or not any(c.isdigit() for c in normalized):
                normalized = None
        elif value and key == "area":
            match = re.fullmatch(r"([\d,]+(?:\.\d+)?)\s*(.*)", value)
            normalized = normalizer.normalize_number(match.group(1)) if match else None
            unit = normalizer.normalize_area_unit(match.group(2)) if match and match.group(2) else None
            record.fields["area_unit"] = unit
        elif value and key.endswith("_date"):
            normalized = normalizer.normalize_date(value)
        elif value and key == "area_unit":
            normalized = normalizer.normalize_area_unit(value)
        elif value and key in ("village", "tehsil", "district", "state"):
            if any(c.isdigit() for c in value) or ":" in value or "=" in value:
                normalized = None
        elif value and key == "land_classification":
            normalized = normalizer.normalize_land_classification(value)
        elif value and key == "ownership_type":
            normalized = normalizer.normalize_ownership_type(value)
        if value is not None and normalized is None:
            warnings.append(f"Uncertain {key}; check the original text.")
        observed.setdefault(key, [])
        if value not in observed[key]:
            observed[key].append(value)
        if len(observed[key]) > 1:
            normalized = None
            additional[f"{key}_candidates"] = observed[key]
            warnings.append(f"Conflicting {key} values; review required.")
            if key == "area":
                record.fields["area_unit"] = None
        record.fields[key] = normalized
        record.provenance = [p for p in record.provenance if p.field_name != key]
        record.provenance.append(FieldProvenance(key, raw, normalized, 0.85 if normalized is not None else 0.0,
                                                "LABELED_VALUE", "key_value", context=f"{label}: {raw}"))
    if owners:
        record.persons = owners
    for entity in record.unmapped_entities:
        additional.setdefault(entity.entity_type.value.lower(), []).append(entity.value)
    # Dates/amounts without a trustworthy relationship remain additional evidence.
    if record.fields.get("area") is not None and record.fields["area"] <= 0:
        warnings.append("Area must be positive; review the recognized value.")
        additional["area_candidate"] = record.fields["area"]
        record.fields["area"] = None
    return additional, list(dict.fromkeys(warnings))


def structured_data(fields, persons, *, language=None, document_type=None, additional=None, raw_text=""):
    result = {key: fields.get(key) for key in (
        "survey_number", "khasra_number", "khata_number", "plot_number", "village", "tehsil", "district", "state", "land_classification", "ownership_type")}
    result.update(
        document_language=language, document_type=document_type,
        owner_details=[{key: person.get(key) for key in ("name", "father_or_husband_name", "address")} for person in persons],
        area={"value": fields.get("area"), "unit": fields.get("area_unit")},
        mutation_details=[{"mutation_number": fields.get("mutation_number"), "mutation_date": fields.get("mutation_date")}] if fields.get("mutation_number") or fields.get("mutation_date") else [],
        registration_details={key: fields.get(key) for key in ("registration_number", "registration_date", "registration_office")},
        additional_fields=additional or {}, raw_text=raw_text,
    )
    return result
