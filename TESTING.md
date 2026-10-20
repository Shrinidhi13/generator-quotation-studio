# Verification notes

## Session-only deployment preparation — 20 October 2026

The current app keeps the quotation in the active browser session. Saved-library, Save draft, search, Open and Revise controls have been removed, along with automatic quotation writes to disk. PDF generation and downloads remain, and an optional editable JSON backup can be downloaded or restored. The legacy disk helpers remain available in `storage.py` for compatibility; the app uses only its import/export helpers.

The hosting configuration no longer fixes the server address to localhost. The Windows launcher still binds locally, while a public host selects its own address. Runtime dependencies are pinned to Streamlit 1.65.0, ReportLab 4.4.9 and Pillow 12.3.0. No app secrets or API keys are required. Data files, secrets, environment files and caches are excluded from the intended new repository, and artwork provenance uses source filename IDs instead of private filesystem paths.

The complete current suite passed on 20 October 2026: **98 tests passed in 47.67 seconds**, on Windows with Python 3.12. Coverage includes quotation calculations, all five feature groups, PDF page order, backup validation, current-session isolation and removal of disk persistence from the app. Every UI test rejects calls to the legacy disk save/load/list helpers; the tests also verify that no draft directory is created. Separate visitor sessions do not share customer fields or PDF output. Starting a new quotation clears the previous customer and generated PDF.

The public deployment at https://techno-quotation-studio.streamlit.app/ was verified on 20 October without a hosting-account login. A demonstration 500 kVA twin quotation was generated and downloaded from the hosted app: equipment 3,900,000 + transportation 40,000 + GST 709,200 = 4,649,200. Its downloaded PDF has six pages, all five feature groups, pricing on page 5 and commercial terms on page 6; extracted text stays within page bounds. At a 390-pixel mobile viewport, the app's document width is 390 pixels with no horizontal overflow.

The results below document earlier visual and browser checks. Saved-library and disk-write results describe removed app behavior. A successful local suite does not by itself verify a hosted deployment.

## Historical local verification — 12–15 October 2026

These checks ran on Windows with Python 3.12. On 15 October, all **16 PDF tests passed** after adding support for three-line postal addresses on the cover, including recipient/address and long-address overflow regressions. The revised cover and pricing-page address layout was also rendered and visually inspected.

### Automated checks

On 12 October, the earlier local edition recorded **95 tests passed** across the domain, storage, PDF and Streamlit UI suite, including 15 PDF cases for all five feature groups, mixed-capacity profiles, six-page standard layouts and content preservation. Three additional UI cases covered custom Other sources across save/reopen, revision, export and PDF generation, source switching, download invalidation and older backups.

- Known amount: DG 385,000 + freight 8,000 + included AMF 16,500 + installation 25,000 = basic 434,500; GST at the configured 18% = 78,210; total = **512,710**.
- Quantity applies to equipment; freight remains once per offer. AMF has its own quantity. Optional AMF/Other charges and their GST are excluded from the offer total.
- Equipment discount precedes tax, with decimal half-up rounding per line.
- Alternative capacities retain separate totals. Combined purchase explicitly sums included lines.
- Rejected negative, nonfinite and invalid values; malformed backups, invalid IDs, duplicate option IDs, path traversal, unsupported schema versions and revision overflow.
- In the earlier local edition, incomplete valid drafts saved/reloaded, revisions preserved original records, and atomic writes left prior saved content intact after a failed replacement. The current app does not expose these persistence operations.
- PDF checks confirm references, long customer/charge/terms text, escaped characters, prices and specification provenance survive pagination. Extracted words remain within page bounds.
- UI checks cover charge removal, multi-capacity selection, included/optional charges, combined totals, saved revisions, validation recovery and invalidation of PDFs after edits.
- The redesigned PDFs add checks that ordinary pricing and its total remain together, twin comparison/combined quotes have no orphan pages, and updating the PDF design invalidates an old download.
- Page-order checks ensure equipment features/specifications precede pricing and commercial terms follow all pricing. Ordinary offers are second-last and terms last; oversized schedules and terms may continue across pages without losing content.
- Feature checks require all five groups before the specifications: product salient features, engine, alternator, controller and acoustic enclosure. They also verify substantive controller protections/interfaces and enclosure descriptions. Coverage includes the legacy single-phase profile, brochure-backed electronic/24 V twin profile, pending 400 kVA configuration and a mixed legacy/twin quotation with separate feature pages. The legacy single-phase feature page does not inherit the old 415 V or 10% imbalance statements.

### Visual PDF review

All pages of the then-current samples were rendered and inspected:

- Single capacity with included extras: **6 pages**.
- 400/500 kVA alternatives: **6 pages**.
- Combined 400/500 kVA purchase: **6 pages**.

The v6 customer-facing design uses a dedicated ivory proposal cover, large capacity typography, representative product artwork, graphite equipment panels and embedded Manrope/Space Grotesk typefaces. Covers contain no prices. Two illustrated feature pages restore all five groups: product highlights with engine/alternator descriptions, followed by controller and acoustic-enclosure details. Technical specifications follow, then pricing on page 5 and final commercial terms on page 6 in the standard examples. The 500 kVA twin has its own brochure-backed features. The 400 kVA confirmation note remains with its option and does not inherit another model's features. All 18 sample pages were rendered and reviewed; feature pages were also inspected at full size. No isolated image/source-note page, cropped table, dropped terms or overlapping text was found. Original letterhead graphics remain in assets.

### Browser checks

Real Chrome browser checks passed for required-field feedback, entered prices, installation totals, quotation download and parsed downloaded-PDF contents, stale-download removal after an edit, adding a 500 kVA option, switching to combined purchase and regenerating the PDF. Desktop screenshots and a separate **390 × 844** mobile check were inspected; the mobile document and main content both measured 390 pixels wide with no horizontal overflow or browser page errors.

With the v6 design, a fresh quotation was generated and downloaded through Chrome with no browser page errors. Its cover without prices, all five feature groups across two pages, specifications, correct total on the second-last page, final commercial terms and embedded display fonts were verified from the downloaded file. These checks used a local preview on 127.0.0.1.

The custom-reference update was also checked in the in-app browser: its downloaded PDF retained the typed reference source and correctly calculated equipment, transport and GST. Customer records and quotation outputs are excluded from the distributable project.

## Scope and limits

- Sample prices are explicitly labelled as illustrative. No product prices have been researched or inferred from the brochure.
- 500 kVA specifications were transcribed from the supplied brochure. 400 kVA is a requested configuration with technical specifications and availability unverified.
- Legacy catalog values and phase availability have not been independently recertified.
- The current edition is prepared for local use or public Streamlit hosting, with one quotation per active browser session and no shared saved-quotation library, cloud sync, database or email sending. The historical checks above do not certify a public deployment.
- PDF text uses embedded Latin fonts; complex-script shaping (for example Marathi) is not included in this version.
- Automated page-bound checks complement the rendered-page review; no printer-specific output was tested.
- This edition is intended for a separate repository from the original GitHub source project.

## Reproduce

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The historical checks used Streamlit 1.65.0, ReportLab 4.4.9, Pillow 12.3.0, pytest 9.1.1, pypdf 6.10.0 and PyMuPDF 1.28.2.
