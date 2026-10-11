import os
from dataclasses import dataclass, field
from typing import Any

import pymupdf
from PIL import Image, UnidentifiedImageError


class DocumentParsingError(Exception):
    """Raised when document content parsing fails with sanitized error description."""



@dataclass
class ParsedDocumentResult:
    """Encapsulates extracted content and structured metadata from parsed documents."""

    raw_text: str | None
    pages: list[dict[str, Any]]
    page_count: int
    requires_ocr: bool
    metadata_json: dict[str, Any] = field(default_factory=dict)


def parse_pdf(file_path: str) -> ParsedDocumentResult:
    """Extracts text page by page from PDF using PyMuPDF and flags documents requiring OCR."""
    if not os.path.isfile(file_path):
        raise DocumentParsingError("Document file not found on storage disk.")

    try:
        doc = pymupdf.open(file_path)
    except Exception as exc:
        raise DocumentParsingError("Failed to parse PDF document: File is corrupted or unreadable.") from exc

    try:
        pages: list[dict[str, Any]] = []
        raw_text_parts: list[str] = []
        total_text_length = 0

        for page_index in range(len(doc)):
            page = doc[page_index]
            page_text = page.get_text() or ""
            stripped_text = page_text.strip()

            pages.append(
                {
                    "page_number": page_index + 1,
                    "text": page_text,
                    "char_count": len(page_text),
                }
            )

            if stripped_text:
                raw_text_parts.append(page_text)
                total_text_length += len(stripped_text)

        page_count = len(doc)
        combined_text = "\n\n--- Page Break ---\n\n".join(raw_text_parts) if raw_text_parts else None

        # Flag as requiring OCR if page count > 0 but no meaningful text could be extracted
        requires_ocr = (page_count > 0 and total_text_length == 0)

        pdf_meta = {
            "format": "PDF",
            "page_count": page_count,
            "title": doc.metadata.get("title") if doc.metadata else None,
            "author": doc.metadata.get("author") if doc.metadata else None,
        }

        return ParsedDocumentResult(
            raw_text=combined_text,
            pages=pages,
            page_count=page_count,
            requires_ocr=requires_ocr,
            metadata_json=pdf_meta,
        )
    except DocumentParsingError:
        raise
    except Exception as exc:
        raise DocumentParsingError(f"Failed to extract content from PDF document: {exc}") from exc
    finally:
        doc.close()


def parse_image(file_path: str) -> ParsedDocumentResult:
    """Inspects and validates an image file using Pillow, extracting format and dimension metadata."""
    if not os.path.isfile(file_path):
        raise DocumentParsingError("Document file not found on storage disk.")

    try:
        with Image.open(file_path) as img:
            # Force load image data to catch truncated or corrupted image content
            img.load()
            width, height = img.size
            img_format = img.format or "UNKNOWN"
            mode = img.mode

        metadata = {
            "format": img_format,
            "width": width,
            "height": height,
            "mode": mode,
        }

        pages = [
            {
                "page_number": 1,
                "text": "",
                "char_count": 0,
            }
        ]

        return ParsedDocumentResult(
            raw_text=None,
            pages=pages,
            page_count=1,
            requires_ocr=False,
            metadata_json=metadata,
        )
    except (UnidentifiedImageError, OSError) as exc:
        raise DocumentParsingError("Failed to decode image: File is corrupted or contains invalid image data.") from exc
    except Exception as exc:
        raise DocumentParsingError(f"Failed to inspect image file: {exc}") from exc


def parse_document(file_path: str, content_type: str) -> ParsedDocumentResult:
    """Dispatches document to appropriate parser based on content_type."""
    if content_type == "application/pdf":
        return parse_pdf(file_path)
    elif content_type in ("image/png", "image/jpeg"):
        return parse_image(file_path)
    else:
        raise DocumentParsingError(f"Unsupported document content type: '{content_type}'")
