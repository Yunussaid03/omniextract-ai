import pymupdf
import pytest
from PIL import Image

from app.processors.document_parser import (
    DocumentParsingError,
    parse_document,
    parse_image,
    parse_pdf,
)


def test_parse_multipage_text_pdf(tmp_path) -> None:
    """Verify PyMuPDF extracts text page-by-page preserving boundaries and page numbers."""
    pdf_path = str(tmp_path / "invoice_multi.pdf")

    # Generate genuine 2-page text PDF using PyMuPDF
    doc = pymupdf.open()
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 72), "Invoice #1001\nVendor: Acme Supplies\nAmount: $450.00")
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 72), "Terms & Conditions\nPayment due within 30 days.")
    doc.save(pdf_path)
    doc.close()

    result = parse_pdf(pdf_path)

    assert result.page_count == 2
    assert result.requires_ocr is False
    assert len(result.pages) == 2
    assert result.pages[0]["page_number"] == 1
    assert "Invoice #1001" in result.pages[0]["text"]
    assert result.pages[1]["page_number"] == 2
    assert "Terms & Conditions" in result.pages[1]["text"]
    assert result.raw_text is not None
    assert "--- Page Break ---" in result.raw_text
    assert result.metadata_json["format"] == "PDF"


def test_parse_textless_pdf_flags_ocr(tmp_path) -> None:
    """Verify blank or textless PDFs are flagged as requires_ocr=True."""
    pdf_path = str(tmp_path / "scanned_doc.pdf")

    # Create PDF with blank pages (no extractable text)
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)
    doc.save(pdf_path)
    doc.close()

    result = parse_pdf(pdf_path)

    assert result.page_count == 1
    assert result.requires_ocr is True
    assert result.raw_text is None
    assert result.pages[0]["text"] == ""


def test_parse_corrupt_pdf(tmp_path) -> None:
    """Verify corrupted PDF triggers DocumentParsingError with sanitized message."""
    corrupt_path = str(tmp_path / "corrupt.pdf")
    with open(corrupt_path, "wb") as f:
        f.write(b"%PDF-1.4 \x00\xff invalid header and trailing noise")

    with pytest.raises(DocumentParsingError) as exc_info:
        parse_pdf(corrupt_path)

    assert "Failed to parse PDF document" in str(exc_info.value)
    # Ensure sensitive paths are not exposed
    assert corrupt_path not in str(exc_info.value)


def test_parse_valid_png_image(tmp_path) -> None:
    """Verify PNG image dimension and format inspection using Pillow."""
    img_path = str(tmp_path / "sample_receipt.png")

    img = Image.new("RGBA", (800, 600), color=(255, 0, 0, 255))
    img.save(img_path, format="PNG")

    result = parse_image(img_path)

    assert result.page_count == 1
    assert result.requires_ocr is False
    assert result.metadata_json["format"] == "PNG"
    assert result.metadata_json["width"] == 800
    assert result.metadata_json["height"] == 600
    assert result.metadata_json["mode"] == "RGBA"


def test_parse_valid_jpeg_image(tmp_path) -> None:
    """Verify JPEG image inspection using Pillow."""
    img_path = str(tmp_path / "waybill.jpg")

    img = Image.new("RGB", (1024, 768), color=(200, 200, 200))
    img.save(img_path, format="JPEG")

    result = parse_image(img_path)

    assert result.page_count == 1
    assert result.requires_ocr is False
    assert result.metadata_json["format"] == "JPEG"
    assert result.metadata_json["width"] == 1024
    assert result.metadata_json["height"] == 768
    assert result.metadata_json["mode"] == "RGB"


def test_parse_corrupt_image(tmp_path) -> None:
    """Verify corrupt image triggers DocumentParsingError with sanitized message."""
    corrupt_path = str(tmp_path / "corrupt.png")
    with open(corrupt_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n truncated data")

    with pytest.raises(DocumentParsingError) as exc_info:
        parse_image(corrupt_path)

    assert "Failed to decode image" in str(exc_info.value)
    assert corrupt_path not in str(exc_info.value)


def test_parse_missing_file() -> None:
    """Verify non-existent file path triggers DocumentParsingError."""
    with pytest.raises(DocumentParsingError) as exc_info:
        parse_document("non_existent_file_path.pdf", "application/pdf")

    assert "Document file not found" in str(exc_info.value)


def test_parse_unsupported_content_type(tmp_path) -> None:
    """Verify unsupported content type triggers DocumentParsingError."""
    sample_path = str(tmp_path / "data.csv")
    with open(sample_path, "w") as f:
        f.write("col1,col2\n1,2")

    with pytest.raises(DocumentParsingError) as exc_info:
        parse_document(sample_path, "text/csv")

    assert "Unsupported document content type" in str(exc_info.value)
