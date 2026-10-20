"""Exercise real form interactions and enforce session-only customer data."""

from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path
import sys

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import storage


@pytest.fixture(autouse=True)
def no_disk_drafts(monkeypatch, tmp_path):
    data_dir = tmp_path / "quotes"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    calls = []

    def reject_disk_access(*args, **kwargs):
        calls.append(True)
        raise AssertionError("The app must never access disk quotation storage.")

    for name in ("save_quote", "load_quote", "list_quotes"):
        monkeypatch.setattr(storage, name, reject_disk_access)
    yield
    assert not calls
    assert not data_dir.exists()


@pytest.fixture
def app():
    instance = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30).run()
    assert not instance.exception
    return instance


def widget(app, kind, label, index=0):
    return [item for item in getattr(app, kind) if item.label == label][index]


def fill_customer_and_price(app):
    widget(app, "text_input", "Lead reference").set_value("LEAD-UI-42")
    widget(app, "text_input", "Quotation number").set_value("TEM/UI/42")
    widget(app, "text_input", "Customer / company name").set_value("Test Engineering")
    widget(app, "number_input", "Price per DG system (₹, before GST)").set_value(500000)
    app.run()
    assert not app.exception


def metric_values(app):
    return [(item.label, item.value) for item in app.metric]


def pdf_text(app):
    return '\n'.join(page.extract_text() for page in PdfReader(BytesIO(app.session_state.pdf_bytes)).pages)


def open_backup(app, monkeypatch, content):
    # AppTest has no uploader interaction API. Supply an in-memory upload while
    # exercising the app's actual Open backup action, parser and editor reset.
    import streamlit

    with monkeypatch.context() as patch:
        patch.setattr(streamlit, "file_uploader", lambda *args, **kwargs: BytesIO(content))
        app.run()
        widget(app, "button", "Open backup").click().run()
    assert not app.exception


def test_custom_other_reference_survives_backup_restore_and_twin_pdf(app, monkeypatch):
    fill_customer_and_price(app)
    widget(app, "selectbox", "DG capacity").select("500 KVA (250 x 2)").run()
    widget(app, "selectbox", "Reference source").select("Other").run()
    widget(app, "text_input", "Other reference source").set_value("  Test Referrer  ").run()
    assert not app.exception
    assert app.session_state.quote["reference"]["source"] == "Test Referrer"
    backup_bytes = storage.export_quote(app.session_state.quote)
    backup = storage.import_quote(backup_bytes)
    assert backup["schema_version"] == 1
    assert backup["reference"]["source"] == "Test Referrer"

    widget(app, "button", "Generate quotation PDF").click().run()
    assert not app.exception
    assert not app.error
    text = pdf_text(app)
    assert "Test Referrer" in text
    assert "500 kVA" in text
    assert "MT500DR" in text
    widget(app, "button", "＋ New quotation").click().run()
    assert "pdf_bytes" not in app.session_state
    open_backup(app, monkeypatch, backup_bytes)
    assert widget(app, "selectbox", "Reference source").value == "Other"
    assert widget(app, "text_input", "Other reference source").value == "Test Referrer"
    assert app.session_state.quote["reference"]["source"] == "Test Referrer"

    assert app.session_state.quote["id"] == backup["id"]
    assert "pdf_bytes" not in app.session_state
    widget(app, "button", "Generate quotation PDF").click().run()
    assert not app.exception
    assert not app.error
    assert "Test Referrer" in pdf_text(app)


def test_reference_preset_switching_drops_stale_custom_source_and_pdf(app):
    fill_customer_and_price(app)
    widget(app, "selectbox", "Reference source").select("Other").run()
    assert widget(app, "text_input", "Other reference source").value == ""
    assert app.session_state.quote["reference"]["source"] == "Other"
    widget(app, "text_input", "Other reference source").set_value("Test Referrer").run()
    widget(app, "button", "Generate quotation PDF").click().run()
    assert "Test Referrer" in pdf_text(app)

    widget(app, "selectbox", "Reference source").select("Email").run()
    assert not app.exception
    assert app.session_state.quote["reference"]["source"] == "Email"
    assert not [item for item in app.text_input if item.label == "Other reference source"]
    assert "pdf_bytes" not in app.session_state

    widget(app, "selectbox", "Reference source").select("Other").run()
    assert widget(app, "text_input", "Other reference source").value == ""
    widget(app, "text_input", "Other reference source").set_value("   ").run()
    assert app.session_state.quote["reference"]["source"] == "Other"
    widget(app, "text_input", "Other reference source").set_value("Test New Referrer").run()
    assert app.session_state.quote["reference"]["source"] == "Test New Referrer"
    widget(app, "selectbox", "Reference source").select("Meeting").run()
    assert app.session_state.quote["reference"]["source"] == "Meeting"
    widget(app, "button", "Generate quotation PDF").click().run()
    assert not app.exception
    assert not app.error
    text = pdf_text(app)
    assert "Meeting" in text
    assert "Test Referrer" not in text
    assert "Test New Referrer" not in text


def test_preexisting_custom_reference_backup_uses_other_textbox(app, monkeypatch):
    existing = deepcopy(app.session_state.quote)
    existing["reference"]["source"] = "Test Legacy Referrer"
    existing["lead_ref"] = "LEAD-LEGACY-REFERENCE"
    existing["quote_number"] = "TEST-LEGACY-REFERENCE"
    # Simulate an existing schema-1 backup, without changing its data shape.
    open_backup(app, monkeypatch, storage.export_quote(existing))
    assert not app.exception
    source = widget(app, "selectbox", "Reference source")
    assert source.value == "Other"
    assert "Test Legacy Referrer" not in source.options
    assert widget(app, "text_input", "Other reference source").value == "Test Legacy Referrer"
    assert app.session_state.quote["reference"]["source"] == "Test Legacy Referrer"


def test_updated_pdf_design_invalidates_previously_generated_download(app, monkeypatch):
    import pdf_export

    fill_customer_and_price(app)
    widget(app, "button", "Generate quotation PDF").click().run()
    assert "pdf_bytes" in app.session_state
    monkeypatch.setattr(pdf_export, "TEMPLATE_VERSION", "changed-design-for-test")
    app.run()
    assert not app.exception
    assert "pdf_bytes" not in app.session_state


def test_new_quotation_has_no_example_customer_or_prices(app):
    original_id = app.session_state.quote["id"]
    assert widget(app, "text_input", "Customer / company name").value == ""
    assert widget(app, "number_input", "Price per DG system (₹, before GST)").value == 0
    assert widget(app, "text_input", "Seller / company").disabled
    widget(app, "button", "＋ New quotation").click().run()
    assert not app.exception
    assert app.session_state.quote["id"] != original_id
    assert not any(item.label in {"Save draft", "Open", "Revise"} for item in app.button)
    assert not any(item.label == "Choose a saved quotation" for item in app.selectbox)
    assert not any(item.label == "Find a quotation" for item in app.text_input)
    assert not any(item.value == "Saved quotations" for item in app.subheader)
    assert any("Quotations are not saved" in item.value for item in app.caption)


def test_multiple_capacities_optional_amf_installation_and_combined_totals(app):
    fill_customer_and_price(app)
    assert ("Quotation total", "₹ 5,90,000.00") in metric_values(app)
    # Field changes and structural actions can arrive in the same browser event.
    widget(app, "text_area", "Additional terms").set_value("Site access by customer.")
    widget(app, "button", "＋ Add another capacity").click().run()
    assert app.session_state.quote["terms"]["additional"] == "Site access by customer."
    assert app.session_state.quote["mode"] == "alternatives"
    widget(app, "selectbox", "DG capacity", 1).select("400 KVA (200 x 2)")
    widget(app, "number_input", "Price per DG system (₹, before GST)", 1).set_value(2000000)
    app.run()
    widget(app, "selectbox", "AMF panel", 0).select("Optional").run()
    widget(app, "number_input", "AMF price per panel (₹, before GST)").set_value(10000).run()
    widget(app, "button", "＋ Add other charge", 0).click().run()
    widget(app, "text_input", "Charge 1 description").set_value("Installation")
    widget(app, "number_input", "Charge price per unit (₹, before GST)").set_value(20000)
    app.run()
    assert not app.exception
    assert ("Option total", "₹ 6,13,600.00") in metric_values(app)
    assert ("Option total", "₹ 23,60,000.00") in metric_values(app)
    assert not any(label == "Combined order total" for label, _ in metric_values(app))
    assert any("₹ 11,800.00" in item.value and "Optional extras" in item.value for item in app.caption)
    widget(app, "toggle", "Combine all capacities in one purchase").set_value(True).run()
    assert ("Combined order total", "₹ 29,73,600.00") in metric_values(app)
    widget(app, "selectbox", "DG capacity", 1).select("500 KVA (250 x 2)").run()
    assert app.session_state.quote["options"][1]["phase"] == "3 Phase"
    assert not app.exception


def test_pdf_persists_and_is_invalidated_by_reference_edits(app):
    fill_customer_and_price(app)
    widget(app, "button", "Generate quotation PDF").click().run()
    assert not app.exception
    assert not app.error
    generated = app.session_state.pdf_bytes
    assert generated.startswith(b"%PDF-")
    app.run()
    assert app.session_state.pdf_bytes == generated
    widget(app, "text_input", "Earlier quotation reference").set_value("TEM/2026/12 dated 01/10/2026")
    widget(app, "date_input", "Meeting / discussion date (optional)").set_value(date(2026, 10, 2))
    widget(app, "text_area", "Reference note").set_value("As discussed by telephone, installation is included.")
    app.run()
    assert "pdf_bytes" not in app.session_state
    assert any("has changed" in item.value for item in app.info)
    assert app.session_state.quote["reference"]["meeting_date"] == "2026-10-02"
    widget(app, "button", "Generate quotation PDF").click().run()
    assert not app.exception
    assert app.session_state.pdf_bytes.startswith(b"%PDF-")


def test_new_quotation_clears_customer_prices_and_generated_pdf(app):
    fill_customer_and_price(app)
    widget(app, "text_input", "Kind attention").set_value("Test contact")
    widget(app, "button", "Generate quotation PDF").click().run()
    original_id = app.session_state.quote["id"]
    assert "pdf_bytes" in app.session_state
    widget(app, "button", "＋ New quotation").click().run()
    assert app.session_state.quote["id"] != original_id
    assert app.session_state.quote["customer"]["name"] == ""
    assert app.session_state.quote["customer"]["attention"] == ""
    assert widget(app, "number_input", "Price per DG system (₹, before GST)").value == 0
    assert "pdf_bytes" not in app.session_state
    assert not app.exception


def test_separate_visitors_never_share_customer_data_or_pdf(app):
    fill_customer_and_price(app)
    widget(app, "button", "Generate quotation PDF").click().run()
    first_id = app.session_state.quote["id"]
    first_pdf = app.session_state.pdf_bytes
    other = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30).run()
    assert not other.exception
    assert other.session_state.quote["id"] != first_id
    assert other.session_state.quote["customer"]["name"] == ""
    assert "pdf_bytes" not in other.session_state
    widget(other, "text_input", "Customer / company name").set_value("Other Test Visitor").run()
    app.run()
    assert app.session_state.quote["customer"]["name"] == "Test Engineering"
    assert app.session_state.pdf_bytes == first_pdf
    assert "Other Test Visitor" not in pdf_text(app)
    widget(other, "button", "＋ New quotation").click().run()
    assert app.session_state.quote["id"] == first_id
    assert app.session_state.quote["customer"]["name"] == "Test Engineering"


def test_invalid_backup_does_not_replace_current_customer_or_pdf(app, monkeypatch):
    fill_customer_and_price(app)
    widget(app, "button", "Generate quotation PDF").click().run()
    before = deepcopy(app.session_state.quote)
    pdf_before = app.session_state.pdf_bytes
    open_backup(app, monkeypatch, b'{invalid JSON')
    assert app.session_state.quote == before
    assert app.session_state.pdf_bytes == pdf_before
    assert any("could not be opened" in error.value for error in app.error)


def test_invalid_discount_is_recoverable_without_crashing_backup_controls(app):
    fill_customer_and_price(app)
    widget(app, "number_input", "Equipment discount (₹)").set_value(600000).run()
    assert not app.exception
    assert any("Discount" in item.value or "discount" in item.value for item in app.warning)
    widget(app, "button", "Generate quotation PDF").click().run()
    assert any("discount" in item.value.casefold() for item in app.error)
    assert "pdf_bytes" not in app.session_state
    widget(app, "number_input", "Equipment discount (₹)").set_value(10000).run()
    assert not app.exception
    assert ("Quotation total", "₹ 5,78,200.00") in metric_values(app)
    widget(app, "button", "Generate quotation PDF").click().run()
    assert not app.error
    assert "5,78,200.00" in pdf_text(app)


def test_removing_an_extra_preserves_remaining_charge_values(app):
    fill_customer_and_price(app)
    widget(app, "button", "＋ Add other charge").click().run()
    widget(app, "text_input", "Charge 1 description").set_value("Installation")
    widget(app, "number_input", "Charge price per unit (₹, before GST)").set_value(20000)
    widget(app, "button", "＋ Add other charge").click().run()
    widget(app, "text_input", "Charge 2 description").set_value("Unloading")
    widget(app, "number_input", "Charge price per unit (₹, before GST)", 1).set_value(3000)
    widget(app, "button", "Remove charge", 0).click().run()
    assert not app.exception
    assert len(app.session_state.quote["options"][0]["others"]) == 1
    assert app.session_state.quote["options"][0]["others"][0]["description"] == "Unloading"
    assert ("Quotation total", "₹ 5,93,540.00") in metric_values(app)
