"""Document image preprocessing – smart pipeline that avoids over-processing clean scans."""

from app.services.preprocessing.preprocessor import DocumentPreprocessor, PreprocessingResult

__all__ = ["DocumentPreprocessor", "PreprocessingResult"]
