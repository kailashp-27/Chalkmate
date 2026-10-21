import io

from PIL import Image
from pypdf import PdfReader

MAX_PAGES = 30
MAX_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def inspect_document(content: bytes, content_type: str):
    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
            raise ValueError("Use an unencrypted PDF with 1–30 pages")
        return len(reader.pages)
    with Image.open(io.BytesIO(content)) as image:
        if image.format not in ("JPEG", "PNG") or image.width * image.height > MAX_PIXELS:
            raise ValueError("Use a JPEG/PNG image of at most 25 megapixels")
        image.verify()
    return 1


def extract_embedded(content: bytes, content_type: str):
    if content_type != "application/pdf":
        return []
    reader = PdfReader(io.BytesIO(content))
    return [
        {"page": number, "text": (page.extract_text() or "")[:50000]}
        for number, page in enumerate(reader.pages, 1)
    ]


def render_pages(content: bytes, content_type: str):
    if content_type == "application/pdf":
        import pypdfium2 as pdfium

        with pdfium.PdfDocument(content) as document:
            if len(document) > 10:
                raise ValueError("Vision extraction supports at most 10 pages per paper")
            for page in document:
                try:
                    bitmap = page.render(scale=1.5)
                    try:
                        image = bitmap.to_pil()
                        image.thumbnail((1800, 2400))
                        result = io.BytesIO()
                        image.convert("RGB").save(result, format="JPEG", quality=85)
                        yield result.getvalue()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
    else:
        with Image.open(io.BytesIO(content)) as image:
            image.thumbnail((1800, 2400))
            result = io.BytesIO()
            image.convert("RGB").save(result, format="JPEG", quality=85)
            yield result.getvalue()
