"""
PDF backends - abstraction layer for PDF parsing libraries.
"""

from .base import DocumentBackend, PageBackend
from .pymupdf import PyMuPDFBackend

__all__ = ["DocumentBackend", "PageBackend", "PyMuPDFBackend"]
