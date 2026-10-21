"""Resources and student responses must be real documents, not matching headers."""

import io

import pytest
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfWriter

from chalkmate.storage import validate_file


@pytest.mark.parametrize(
    "name,data",
    [
        ("fake.pdf", b"%PDF-1.4\n%%EOF"),
        ("fake.png", b"\x89PNG\r\n\x1a\nnot an image"),
        ("fake.jpg", b"\xff\xd8\xffinvalid"),
    ],
)
def test_invalid_documents_are_rejected(name, data):
    with pytest.raises(HTTPException) as failure:
        validate_file(name, data)
    assert failure.value.status_code == 415


def test_encrypted_pdf_rejected_and_valid_image_accepted():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("synthetic-test-password")
    writer.write(output)
    with pytest.raises(HTTPException):
        validate_file("encrypted.pdf", output.getvalue())
    image = io.BytesIO()
    Image.new("RGB", (12, 12), "white").save(image, format="PNG")
    assert validate_file("resource.png", image.getvalue()) == "image/png"
