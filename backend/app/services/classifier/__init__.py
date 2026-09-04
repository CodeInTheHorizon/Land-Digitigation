"""Document classification service for Indian land records.

Classifies documents into one of 10 categories using a multi-signal
approach: keyword matching, structural patterns, and header analysis.
Pure business logic — no DB imports.
"""

from __future__ import annotations

from .document_classifier import (
    ClassificationResult,
    DocumentCategory,
    DocumentClassifier,
)

__all__ = [
    "ClassificationResult",
    "DocumentCategory",
    "DocumentClassifier",
]
