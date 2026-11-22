# 008 Optional PDF report reading: requirements

Status: done

## Why

Search results often include PDF reports (for example consulting or industry reports). The scraper read only HTML, so these fell back to the search snippet. Reading PDFs is slower and the text is noisier, so it should be the user's choice.

## Acceptance criteria

- **R1** A `READ_PDFS` setting (default off) and a "Read PDF reports" switch in the sidebar control PDF reading. The switch is disabled when page reading is off.
- **R2** When off, a PDF result keeps its snippet and the reason says "PDF report (PDF reading is off)".
- **R3** When on, the scraper reads the first 20 pages of PDFs up to 10 MB and keeps the most relevant passage, with the same scoring, masking and trimming as web pages. The model sees one passage per source, so token use does not grow.
- **R4** Encrypted, broken or oversized PDFs never fail the run; they report a reason and keep the snippet.
- **R5** robots.txt and the public-address check apply to PDFs exactly as to web pages.

## Traceability

| Criterion | Code | Tests |
| --- | --- | --- |
| R1 | `config.read_pdfs`, `pipeline`, `streamlit_app.sidebar` | `test_pdf_switch_reaches_the_pipeline` |
| R2 | `PageScraper._fetch_paragraphs` | `test_pdfs_are_skipped_when_reading_is_off`, `test_unusable_pages_report_a_reason` |
| R3 | `scraper.pdf_paragraphs`, `scraper.best_passage` | `test_pdf_paragraphs_extract_report_text`, `test_pdfs_give_a_passage_when_reading_is_on` |
| R4 | `scraper.pdf_paragraphs`, `PageScraper._fetch_paragraphs` | `test_broken_or_oversized_pdfs_report_a_reason` |
| R5 | `PageScraper.scrape` | shared with spec 004 and 007 tests |

## Tasks

- [x] **T1** Setting, sidebar switch and pipeline wiring.
- [x] **T2** PDF text extraction with `pypdf`, page and size limits, and tests with a generated PDF.
- [ ] **T3** Live check on a real report with the switch on and off.
