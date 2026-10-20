# Generator Quotation Studio

[Open the quotation app](https://techno-quotation-studio.streamlit.app/) — available on laptop and mobile through Streamlit Community Cloud.

A simple quotation desk for Techno Electromechs, built from the existing Generator Quotation App. All code, original PNG assets and the supplied twin-genset brochure are included. This edition has its own repository, `generator-quotation-studio`, separate from the original GitHub project.

Create a quotation, download its PDF and start the next one. The current quotation is held only for the active browser session: there is no saved-quotation library or automatic saving to the computer or shared server. Closing or refreshing the page may clear the form. An optional editable JSON backup lets you download your work and restore it later.

## Start locally

On Windows, double-click **START_APP.bat**. First launch sets up the required Python packages, so an internet connection is needed once. It uses Python 3.11 or newer, or the installed Codex Python runtime when available. Then open **http://127.0.0.1:8501**. Keep the app's terminal window open while using it; close it to stop the app.

If port 8501 is already in use, open the existing app or choose another port in the manual launch command.

Manual setup, including macOS/Linux:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## Publish on Streamlit Community Cloud

1. Put this app folder's contents at the root of the new `generator-quotation-studio` GitHub repository. Include `app.py`, `requirements.txt`, `.streamlit/config.toml` and all assets. Keep customer records, virtual environments and secrets out of the repository.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app from the new repository and its published branch. Set the main file path to `app.py`.
3. In Advanced settings, select **Python 3.12**. Leave Secrets empty: this app needs no API keys or external service credentials.
4. Deploy, then use the URL that Streamlit assigns. A public deployment lets visitors generate quotations in their own sessions; it has no shared quotation library or cloud sync.

See the [official deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy). The app configuration leaves the server address to the hosting platform; the local launcher explicitly binds to `127.0.0.1`.

## Everyday workflow

1. Enter the lead reference, quotation number and customer.
2. Select the capacity, quantity and your selling price. A twin system counts as **one** unit: 500 kVA means 250 kVA × 2.
3. Use **Add another capacity** when the customer needs a comparison. Each capacity has its own total. Turn on **Combine all capacities in one purchase** only when the customer is buying all of them.
4. Expand **Reference & earlier discussions** for a meeting/discussion date, earlier quotation or telephone note. Choose **Other** to type a referrer's name or any custom source. The entered source appears in the PDF and in an editable backup if you download one.
5. Expand **AMF, installation & other charges** for installation, cabling, unloading or any other item. Included charges enter the total; optional charges are quoted separately, including their GST.
6. Generate the PDF, review it and download it. The product overview, feature pages and technical specifications come first, followed by pricing and then commercial terms. The equipment-details checkbox includes all applicable feature groups and specifications. Any edit makes the previous PDF unavailable until regenerated.

Use **New quotation** to clear the editor and start again. Download the PDF or an editable backup first if you want to keep the current quotation. There is no Save draft, saved-quotation search or automatic recovery after the session ends.

The optional **Backup & restore** section offers **Download editable backup** and **Open backup**. Backups can preserve incomplete quotations and restore their fields into the current session. Opening a backup replaces the current form. The app does not add a database, automatic numbering, email sending or a CRM.

## What improved

- One lead can contain several DG capacities, each with its own price, quantity and charges.
- Comparison mode is the default; combined-purchase mode is available when needed.
- Meeting dates, telephone notes, earlier quotations and revision references appear in the PDF.
- “Other charges” supports descriptions, quantities, prices, tax rates and optional status.
- Added **400 kVA (200 × 2)** and **500 kVA (250 × 2)**.
- Clear included/optional AMF handling; included AMF now contributes to tax and totals.
- Decimal-based, item-level rounding; equipment discount before tax; transport is once per option.
- Cleaner PDF overview, all five original product feature groups with model-specific qualifications, technical specifications, flowing pricing tables, commercial terms and page numbers. Long content continues onto additional pages instead of disappearing.
- A session-only quotation form, optional editable backup/restore and editable commercial terms.
- Central catalog shared by the UI and PDF. Original assets load from the app folder regardless of launch directory.

## Catalog and commercial details

The supplied brochure establishes the **500 kVA / MT500DR** configuration, including 400 kW output, 415 V three-phase, 780 L fuel tank and approximate dimensions 8800 × 1600 × 1975 mm. Its product image is representative of the brochure's twin DG family.

The brochure **does not cover 400 kVA (200 × 2)**. That requested choice is available with its technical details and availability explicitly marked for supplier confirmation; no model, tank or dimensions have been invented.

Original 5–320 kVA values and starred variants are retained in `assets/legacy-catalog.json` and qualified as legacy data. Phase availability and current specifications should be confirmed with the supplier. The app does not assert 415 V for a single-phase selection or apply generic technical/warranty claims to all capacities.

Legacy product feature descriptions are adapted from the older quotation reference with model-specific qualifications; they are not asserted as features of every DG capacity. The **500 kVA** feature profile uses the supplied twin-genset brochure. The **400 kVA** profile remains pending supplier confirmation and does not borrow unverified features from the 500 kVA or legacy profiles. The package includes [equipment_features.py](equipment_features.py) and [feature source notes](assets/equipment-feature-sources.json), but does not include the full customer quotation used as a reference.

The original warranty statements conflicted. The new app uses one editable warranty term referencing the applicable manufacturer policy. GST defaults to the original app's 18%, remains editable per charge, and is a quotation setting rather than a verified tax determination. Payment, delivery, validity, exclusions and additional terms are editable. Installation is excluded only when it is not explicitly priced as included. Freight does not imply transit insurance. The original cancellation/arbitration wording is retained in editable additional terms.

## PDF design and assets

The default customer PDF presents the **cover → applicable product feature pages → technical specifications → offer and price schedule → commercial terms**. The feature section covers the five original groups: **Product highlights, Engine, Alternator, Controller and Acoustic enclosure**, with information qualified for the selected model. The cover introduces the customer and selected capacities without showing prices. It preserves up to three postal-address lines; longer addresses appear in full with the price schedule. In a standard quotation, pricing is on the second-last page and commercial terms are on the last page.

Turning off equipment details omits all feature groups and specifications, leaving the cover, pricing and terms. A 400 kVA-only quotation keeps the pending-specification notice without adding unsupported feature pages; quotations mixing legacy and 500 kVA models can have separate feature pages. Large quotations, long schedules or extended terms can flow onto additional pages while retaining this section order.

The design uses premium graphite, ivory and red, a crisp text letterhead, prominent capacity panels, five-column pricing tables and separate optional extras. Embedded **Manrope** and **Space Grotesk** fonts are licensed under SIL Open Font License 1.1; see the [font sources and embedding notes](assets/fonts/README.txt), [Manrope license](assets/fonts/Manrope-OFL.txt) and [Space Grotesk license](assets/fonts/SpaceGrotesk-OFL.txt). Seller contact fields affect the closing section; a GSTIN is printed only when supplied in the seller fields.

`product-single-premium.png` and `product-twin-premium.png` are representative product artwork created through generated background cleanup of the original images. They are not exact archival photographs or technical references; [artwork provenance](assets/product-artwork-provenance.json) records the sources, edits and limitations. All original assets, including the PNG letterhead and [source twin-genset brochure](assets/TWIN_GENSET_Brochure.pdf), are retained for reference. Technical specifications come from the catalog and brochure evidence, never from the cleaned artwork.

## Sample quotations

The `examples` folder contains:

- `sample-single.pdf` — one capacity, included AMF and installation.
- `sample-alternatives.pdf` — 400/500 kVA alternatives, revision/reference and optional AMF.
- `sample-combined.pdf` — the same capacities as one combined purchase.
- Two matching `.json` examples that can be opened through Backup & restore.

The sample layout follows the same reading order: a cover without prices, applicable product feature groups, technical specifications, pricing and commercial terms last. All examples are marked as demonstrations. Their prices are illustrative, not a price list. The app itself starts with blank customer information and zero prices.

## Files and maintenance

| File/folder | Purpose |
|---|---|
| `app.py` | Session-only Streamlit form, PDF download and optional backup/restore |
| `domain.py` | Validation, pricing, revisions and filenames |
| `catalog.py` | One shared catalog with source qualifications |
| `equipment_features.py` | Model-qualified profiles for all five product feature groups |
| `storage.py` | Backup validation/import/export; legacy disk helpers are not used by the app |
| `pdf_export.py` | Flowing branded PDF generation |
| `assets/` | Original PNGs, brochure, extracted twin PNGs, feature source JSON and artwork provenance |
| `data/` | Legacy local data, unused by the app and excluded from Git except `.gitkeep` |
| `examples/` | Clearly labelled demonstration PDFs and backups |
| `tests/` | Calculation, persistence, PDF and UI regression tests |

To run automated checks:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Runtime dependencies are pinned to Streamlit 1.65.0, ReportLab 4.4.9 and Pillow 12.3.0. Python 3.12 matches the historical local verification environment. See [TESTING.md](TESTING.md) for verification history and current limits. Keep virtual environments, caches, customer records and secrets out of the new repository; `.gitignore` includes these exclusions.

Source baseline: https://github.com/Shrinidhi13/generator-app, commit `f1072af54413788e532e561a99620bacca256fc1`. Brochure: the user-supplied `TWIN GENSET_Brochure_Final.pdf`; a local copy is included in assets. No new ownership or redistribution license is assigned to the original branding or brochure.
