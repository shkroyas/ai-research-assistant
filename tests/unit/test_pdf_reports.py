"""Optional PDF report reading in the scraper (spec 008)."""

import httpx

from market_research.scraper import PageScraper, pdf_paragraphs

QUERY = "AI adoption in banking"
TEXT = [
    "Annual banking trends report.",
    "AI adoption in banking reached 72% of large banks in 2024, led by fraud detection.",
    "Most banks plan to expand generative AI pilots into customer service next year.",
]


def make_pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with one line of text per entry."""
    ops = "BT /F1 10 Tf 40 760 Td 14 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
    stream = ops.encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def scraper_for(body: bytes, **kwargs) -> PageScraper:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=body, headers={"content-type": "application/pdf"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    public = lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))]  # noqa: E731
    return PageScraper(client=client, resolve=public, **kwargs)


def test_pdf_paragraphs_extract_report_text() -> None:
    paragraphs = pdf_paragraphs(make_pdf(TEXT), max_pages=5)
    assert any("72% of large banks" in p for p in paragraphs)


def test_pdfs_are_skipped_when_reading_is_off() -> None:
    result = scraper_for(make_pdf(TEXT)).scrape("https://r.example/report.pdf", QUERY)
    assert not result.ok and result.reason == "PDF report (PDF reading is off)"


def test_pdfs_give_a_passage_when_reading_is_on() -> None:
    result = scraper_for(make_pdf(TEXT), read_pdfs=True).scrape("https://r.example/r.pdf", QUERY)
    assert result.ok and result.passage and "72% of large banks" in result.passage


def test_broken_or_oversized_pdfs_report_a_reason() -> None:
    broken = scraper_for(b"%PDF-1.4 not really a pdf", read_pdfs=True)
    assert broken.scrape("https://r.example/a.pdf", QUERY).reason == "PDF could not be read"
    big = scraper_for(make_pdf(TEXT), read_pdfs=True, max_pdf_bytes=100)
    assert big.scrape("https://r.example/b.pdf", QUERY).reason == "PDF larger than the size limit"
