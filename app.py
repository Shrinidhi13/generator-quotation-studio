"""A simple quotation generator; customer data stays in its browser session."""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import date
import hashlib
import json
from decimal import Decimal

import streamlit as st

from catalog import CATALOG
from domain import (
    calculate_option,
    money,
    new_charge,
    new_option,
    new_quote,
    quote_filename,
    validate_quote,
)
from pdf_export import create_pdf, TEMPLATE_VERSION
from storage import export_quote, import_quote


st.set_page_config(
    page_title="Generator quotations · Techno Electromechs",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html("""
<style>
  :root { color-scheme: light; }
  .stApp { background: #f7f5f0; }
  .stMainBlockContainer { max-width: 1050px; padding-top: 2.5rem; padding-bottom: 4rem; }
  h1, h2, h3 { color: #172b42; letter-spacing: -.025em; }
  h1 { font-size: 2.35rem !important; padding-bottom: .2rem !important; }
  h2 { font-size: 1.3rem !important; }
  h3 { font-size: 1.12rem !important; }
  [data-testid="stSidebar"] { background: #eeece5; border-right: 1px solid #dfded6; }
  [data-testid="stSidebar"] h2 { font-size: 1.05rem !important; }
  [data-testid="stVerticalBlockBorderWrapper"] > div { border-radius: 14px; }
  [data-testid="stMetricValue"] { color: #172b42; font-size: 1.4rem; }
  [data-testid="stMetricLabel"] { color: #5a6672; }
  button[kind="primary"] { background-color: #b13c36; border-color: #b13c36; }
  button[kind="primary"]:hover { background-color: #94332e; border-color: #94332e; }
  [data-testid="stExpander"] { background: #ffffff66; border-radius: 10px; }
  [data-testid="stTextInput"] input,
  [data-testid="stNumberInput"] input,
  [data-testid="stTextArea"] textarea { background: #fff; }
  [data-testid="stCaptionContainer"] { color: #586575; }
  @media (max-width: 640px) {
    .stMainBlockContainer { padding-top: 1.4rem; }
    h1 { font-size: 1.85rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.15rem; }
  }
</style>
""")


def fingerprint(quote: dict) -> str:
    canonical = deepcopy(quote)
    canonical['_pdf_template_version'] = TEMPLATE_VERSION
    # Number widgets format values to two decimals; formatting alone is not an edit.
    for option in canonical["options"]:
        for field in ("unit_price", "gst_rate", "discount", "transport", "transport_gst", "amf_price", "amf_gst"):
            option[field] = format(Decimal(str(option[field])).normalize(), "f")
        for charge in option["others"]:
            for field in ("unit_price", "gst_rate"):
                charge[field] = format(Decimal(str(charge[field])).normalize(), "f")
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


if "quote" not in st.session_state:
    st.session_state.quote = new_quote()
    st.session_state.editor_epoch = 0


def key(name: str) -> str:
    return f"edit_{st.session_state.editor_epoch}_{name}"


def refresh_editor() -> None:
    """Rebuild indexed widgets after additions, removals, or document changes."""
    for widget_key in list(st.session_state):
        if widget_key.startswith("edit_"):
            del st.session_state[widget_key]
    st.session_state.editor_epoch += 1


def replace_quote(quote: dict) -> None:
    st.session_state.quote = quote
    refresh_editor()
    for name in ("pdf_bytes", "pdf_fingerprint", "pdf_dirty", "validation_errors", "error_fingerprint"):
        st.session_state.pop(name, None)


def amount(label: str, value: str, widget_key: str, *, step: float = 1000.0,
           help: str | None = None) -> str:
    result = st.number_input(
        label, min_value=0.0, max_value=9999999999.99, value=float(value), step=step,
        format="%.2f", key=key(widget_key), help=help,
    )
    return f"{result:.2f}"


def tax_input(label: str, value: str, widget_key: str) -> str:
    result = st.number_input(
        label, min_value=0.0, max_value=100.0, value=float(value),
        step=1.0, format="%.2f", key=key(widget_key),
    )
    return f"{result:.2f}"


def date_value(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


quote = st.session_state.quote
pending_action = None

with st.sidebar:
    st.caption("TECHNO ELECTROMECHS")
    st.subheader("Your quotation desk")
    st.caption("Prepare your quotation, then download the PDF.")
    with st.expander("Seller details"):
        seller = quote["seller"]
        st.text_input("Seller / company", seller["name"], key=key("seller_name"), disabled=True)
        st.caption("The PDF uses a clean Techno Electromechs letterhead. These contact details appear in the closing section.")
        seller["contact"] = st.text_input("Sales contact", seller["contact"], key=key("seller_contact"))
        seller["phone"] = st.text_input("Seller phone", seller["phone"], key=key("seller_phone"))
        seller["email"] = st.text_input("Seller email", seller["email"], key=key("seller_email"))
        seller["address"] = st.text_area("Seller address", seller["address"], key=key("seller_address"))
        seller["gstin"] = st.text_input("Seller GSTIN", seller["gstin"], key=key("seller_gstin"))
    sidebar_documents = st.container()

st.caption("TECHNO ELECTROMECHS  /  SALES DESK")
st.title("Generator quotations")
st.write("A clear offer. The right capacity. Ready for your customer.")
st.caption("Quotations are not saved in the app. Your entries stay in this browser session and may clear when you close or refresh the tab. Download the PDF when ready.")
if quote["revision"]:
    st.caption(f"REVISION {quote['revision']}")
else:
    st.caption("NEW QUOTATION · Add another capacity whenever your customer needs a choice.")

with st.container(border=True):
    st.subheader("Customer & quotation")
    col_lead, col_number, col_date = st.columns([1, 1.1, 1])
    with col_lead:
        quote["lead_ref"] = st.text_input("Lead reference", quote["lead_ref"], key=key("lead_ref"), max_chars=100, placeholder="Your lead number")
    with col_number:
        quote["quote_number"] = st.text_input("Quotation number", quote["quote_number"], key=key("quote_number"), max_chars=100)
    with col_date:
        selected_date = st.date_input("Quotation date", date_value(quote["date"]), format="DD/MM/YYYY", key=key("date"))
        quote["date"] = selected_date.isoformat() if selected_date else ""
    customer = quote["customer"]
    col_name, col_attention = st.columns([1.6, 1])
    with col_name:
        customer["name"] = st.text_input("Customer / company name", customer["name"], key=key("customer_name"), placeholder="Who is this offer for?")
    with col_attention:
        customer["attention"] = st.text_input("Kind attention", customer["attention"], key=key("customer_attention"), placeholder="Contact person's name")
    customer["address"] = st.text_area("Customer address", customer["address"], key=key("customer_address"), height=80, placeholder="Street, city and PIN code")
    with st.expander("Customer contact & GST details"):
        phone_col, email_col = st.columns(2)
        with phone_col:
            customer["phone"] = st.text_input("Customer phone", customer["phone"], key=key("customer_phone"))
        with email_col:
            customer["email"] = st.text_input("Customer email", customer["email"], key=key("customer_email"))
        customer["gstin"] = st.text_input("Customer GSTIN", customer["gstin"], key=key("customer_gstin"))

with st.expander("Reference & earlier discussions"):
    reference = quote["reference"]
    sources = ["Enquiry over telephone", "Meeting", "Email", "IndiaMart", "Walk-in", "Revised quotation", "Other"]
    # Store the entered source directly so existing backups and PDFs retain it.
    current_source = reference["source"]
    source_choice = current_source if current_source in sources else "Other"
    source_col, meeting_col = st.columns(2)
    with source_col:
        selected_source = st.selectbox("Reference source", sources, index=sources.index(source_choice), key=key("reference_source"))
        if selected_source == "Other":
            custom_source = st.text_input(
                "Other reference source",
                value=current_source if current_source not in sources else "",
                key=key("reference_source_other"), max_chars=2000,
                placeholder="Referrer's name or another source",
                help="Enter the person's name or another source. This appears in the quotation reference.",
            )
            reference["source"] = custom_source.strip() or "Other"
        else:
            reference["source"] = selected_source
    with meeting_col:
        meeting_date = st.date_input("Meeting / discussion date (optional)", date_value(reference["meeting_date"]), format="DD/MM/YYYY", key=key("meeting_date"))
        reference["meeting_date"] = meeting_date.isoformat() if meeting_date else ""
    reference["previous_quote"] = st.text_input("Earlier quotation reference", reference["previous_quote"], key=key("previous_quote"), placeholder="Quotation number and date, if applicable")
    reference["discussion"] = st.text_area("Reference note", reference["discussion"], key=key("reference_discussion"), height=80, placeholder="For example: As discussed by telephone, this revision includes installation.")

st.subheader("Generator selection")
if len(quote["options"]) > 1:
    together = st.toggle(
        "Combine all capacities in one purchase",
        value=quote["mode"] == "combined", key=key("combined"),
        help="Leave off to present separate alternatives. Turn on only when the customer intends to buy every selected option.",
    )
    quote["mode"] = "combined" if together else "alternatives"
    st.caption(
        "Combined purchase · All selected generators and included charges form one order total."
        if together else
        "Compare alternatives · Each capacity has its own price. Your customer chooses an option."
    )

option_results = []
for option_index, option in enumerate(quote["options"]):
    prefix = f"option_{option['id']}"
    with st.container(border=True):
        heading_col, remove_col = st.columns([4, 1])
        with heading_col:
            label = "Generator" if len(quote["options"]) == 1 else f"Option {option_index + 1}"
            st.subheader(label)
        with remove_col:
            if len(quote["options"]) > 1 and st.button("Remove", key=key(f"{prefix}_remove"), width="stretch", help=f"Remove option {option_index + 1}"):
                pending_action = ("remove_option", option_index)

        capacity_col, phase_col, quantity_col = st.columns([1.65, 1, .8])
        with capacity_col:
            capacities = list(CATALOG)
            option["capacity"] = st.selectbox("DG capacity", capacities, index=capacities.index(option["capacity"]), key=key(f"{prefix}_capacity"))
        details = CATALOG[option["capacity"]]
        with phase_col:
            phases = details["phase_options"]
            selected_phase = option["phase"] if option["phase"] in phases else phases[0]
            option["phase"] = st.selectbox("Phase", phases, index=phases.index(selected_phase), key=key(f"{prefix}_phase"))
        with quantity_col:
            option["quantity"] = st.number_input("Quantity", min_value=1, max_value=1000, value=int(option["quantity"]), step=1, key=key(f"{prefix}_quantity"))

        if details["twin"]:
            st.caption("Twin genset · Quantity 1 means one complete twin system (two engines).")
            if not details["verified"]:
                st.caption("400 kVA: technical specifications and availability need supplier confirmation; this configuration is not covered in the supplied brochure.")

        price_col, freight_col = st.columns([1.5, 1])
        with price_col:
            option["unit_price"] = amount("Price per DG system (₹, before GST)", option["unit_price"], f"{prefix}_price", help="Enter your selling price for one complete system. For twin models, enter the price of both engines together.")
        with freight_col:
            option["transport"] = amount("Transportation (₹, before GST)", option["transport"], f"{prefix}_transport", step=500.0, help="A single transport charge for this option, regardless of quantity.")

        with st.expander("AMF, installation & other charges"):
            amf_modes = ["Not required", "Included", "Optional"]
            option["amf_mode"] = st.selectbox("AMF panel", amf_modes, index=amf_modes.index(option["amf_mode"]), key=key(f"{prefix}_amf_mode"), help="Included adds the panel to this option's total. Optional shows its price separately.")
            if option["amf_mode"] != "Not required":
                amf_price_col, amf_qty_col, amf_tax_col = st.columns([1.5, .8, .8])
                with amf_price_col:
                    option["amf_price"] = amount("AMF price per panel (₹, before GST)", option["amf_price"], f"{prefix}_amf_price", step=500.0)
                with amf_qty_col:
                    option["amf_quantity"] = st.number_input("AMF quantity", min_value=1, max_value=1000, value=int(option["amf_quantity"]), step=1, key=key(f"{prefix}_amf_quantity"))
                with amf_tax_col:
                    option["amf_gst"] = tax_input("AMF GST (%)", option["amf_gst"], f"{prefix}_amf_gst")
            st.markdown("**Other charges**")
            st.caption("Installation, unloading, cabling or any other item. Optional items are priced separately.")
            for charge_index, charge in enumerate(option["others"]):
                charge_key = f"{prefix}_charge_{charge_index}"
                desc_col, delete_col = st.columns([5, 1])
                with desc_col:
                    charge["description"] = st.text_input(f"Charge {charge_index + 1} description", charge["description"], key=key(f"{charge_key}_description"), max_chars=1000, placeholder="For example, installation and commissioning")
                with delete_col:
                    st.write("")
                    if st.button("Remove charge", key=key(f"{charge_key}_remove"), help=f"Remove charge {charge_index + 1}"):
                        pending_action = ("remove_charge", option_index, charge_index)
                rate_col, count_col, tax_col = st.columns([1.5, .8, .8])
                with rate_col:
                    charge["unit_price"] = amount("Charge price per unit (₹, before GST)", charge["unit_price"], f"{charge_key}_price", step=500.0)
                with count_col:
                    charge["quantity"] = st.number_input("Charge quantity", min_value=1, max_value=1000, value=int(charge["quantity"]), step=1, key=key(f"{charge_key}_quantity"))
                with tax_col:
                    charge["gst_rate"] = tax_input("Charge GST (%)", charge["gst_rate"], f"{charge_key}_gst")
                charge["optional"] = st.checkbox("Optional — exclude from quotation total", value=charge["optional"], key=key(f"{charge_key}_optional"))
                st.divider()
            if st.button("＋ Add other charge", key=key(f"{prefix}_add_charge"), disabled=len(option["others"]) >= 30):
                pending_action = ("add_charge", option_index)

        with st.expander("Tax, discount & notes"):
            discount_col, dg_tax_col, freight_tax_col = st.columns([1.5, 1, 1])
            with discount_col:
                option["discount"] = amount("Equipment discount (₹)", option["discount"], f"{prefix}_discount", step=500.0, help="One flat discount on the full equipment line, applied before GST. Other charges are not discounted.")
            with dg_tax_col:
                option["gst_rate"] = tax_input("Equipment GST (%)", option["gst_rate"], f"{prefix}_gst")
            with freight_tax_col:
                option["transport_gst"] = tax_input("Transportation GST (%)", option["transport_gst"], f"{prefix}_transport_gst")
            option["notes"] = st.text_area("Notes for this option", option["notes"], key=key(f"{prefix}_notes"), max_chars=4000, height=80, placeholder="Specific inclusions, site requirements or product notes")

        try:
            result = calculate_option(option)
            option_results.append(result)
            base_col, gst_col, total_col = st.columns([1, 1, 1.3])
            with base_col:
                st.metric("Before GST", f"₹ {money(result['subtotal'])}")
            with gst_col:
                st.metric("GST", f"₹ {money(result['tax'])}")
            with total_col:
                st.metric("Option total" if len(quote["options"]) > 1 else "Quotation total", f"₹ {money(result['total'])}")
            if result["optional_total"]:
                st.caption(f"Optional extras: ₹ {money(result['optional_total'])} including GST · excluded from the total above.")
        except (ValueError, ArithmeticError, TypeError) as error:
            option_results.append(None)
            st.warning(f"Update this option to calculate its total: {error}")

        with st.expander("Technical details"):
            st.caption(details["spec_note"])
            if details["specs"]:
                st.table({"Specification": list(details["specs"]), "Details": list(details["specs"].values())})

if st.button("＋ Add another capacity", key="add_capacity", disabled=len(quote["options"]) >= 20):
    pending_action = ("add_option",)

if len(quote["options"]) > 1 and quote["mode"] == "combined" and all(option_results):
    with st.container(border=True):
        order_base, order_tax, order_total = st.columns([1, 1, 1.3])
        with order_base:
            st.metric("Order before GST", f"₹ {money(sum(item['subtotal'] for item in option_results))}")
        with order_tax:
            st.metric("Order GST", f"₹ {money(sum(item['tax'] for item in option_results))}")
        with order_total:
            st.metric("Combined order total", f"₹ {money(sum(item['total'] for item in option_results))}")
        st.caption("Includes every selected generator option. Optional extras are excluded.")

with st.expander("Terms & quotation settings"):
    settings_col, specs_col = st.columns(2)
    with settings_col:
        quote["valid_days"] = st.number_input("Offer validity (days)", min_value=1, max_value=365, value=int(quote["valid_days"]), step=1, key=key("valid_days"))
    with specs_col:
        quote["include_specs"] = st.checkbox("Include equipment details in PDF", value=quote["include_specs"], key=key("include_specs"), help="Adds product highlights, engine, alternator, controller and acoustic enclosure descriptions, plus model specifications.")
    terms = quote["terms"]
    for field, title in (("payment", "Payment"), ("delivery", "Delivery"), ("warranty", "Warranty"), ("scope", "Scope of supply"), ("exclusions", "Exclusions"), ("additional", "Additional terms")):
        terms[field] = st.text_area(title, terms[field], key=key(f"terms_{field}"), max_chars=4000, height=85)
    st.caption("Review these terms for this customer before sharing the quotation.")

if pending_action:
    action = pending_action[0]
    if action == "add_option":
        quote["options"].append(new_option())
    elif action == "remove_option":
        quote["options"].pop(pending_action[1])
    elif action == "add_charge":
        quote["options"][pending_action[1]]["others"].append(new_charge())
    elif action == "remove_charge":
        quote["options"][pending_action[1]]["others"].pop(pending_action[2])
    refresh_editor()
    st.rerun()


current_fingerprint = fingerprint(quote)
if st.session_state.get("pdf_fingerprint") and st.session_state.pdf_fingerprint != current_fingerprint:
    st.session_state.pop("pdf_bytes", None)
    st.session_state.pop("pdf_fingerprint", None)
    st.session_state.pdf_dirty = True
if st.session_state.get("error_fingerprint") != current_fingerprint:
    st.session_state.pop("validation_errors", None)

st.divider()
generate_clicked = st.button("Generate quotation PDF", type="primary", width="stretch")

if generate_clicked:
    errors = validate_quote(quote)
    if errors:
        st.session_state.validation_errors = errors
        st.session_state.error_fingerprint = current_fingerprint
    else:
        try:
            with st.spinner("Preparing your quotation…"):
                pdf_bytes = create_pdf(quote)
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.pdf_fingerprint = current_fingerprint
                st.session_state.pdf_dirty = False
                st.session_state.pop("validation_errors", None)
        except Exception as error:
            st.error(f"The PDF could not be created. Your draft is still here. Details: {error}")

if st.session_state.get("validation_errors"):
    st.error("Please complete the following before generating your PDF:\n\n" + "\n".join(f"• {message}" for message in st.session_state.validation_errors))

if st.session_state.get("pdf_bytes"):
    st.success("Your quotation is ready to review and download.")
    st.download_button(
        "Download quotation PDF", data=st.session_state.pdf_bytes,
        file_name=quote_filename(quote), mime="application/pdf",
        type="primary", width="stretch", on_click="ignore",
    )
    with st.expander("Preview quotation", expanded=True):
        encoded_pdf = base64.b64encode(st.session_state.pdf_bytes).decode("ascii")
        st.iframe(
            f"data:application/pdf;base64,{encoded_pdf}",
            height=780, alt="Generated customer quotation PDF preview",
        )
        st.caption("If the preview is unavailable in your browser, download the PDF to review it.")
elif st.session_state.get("pdf_dirty"):
    st.info("This quotation has changed. Generate the PDF again to include your latest edits.")
else:
    st.caption("Your PDF will include customer details, prices, references and terms. Enter your current selling prices before generating it.")

# Render navigation after the editor so every new widget value is captured
# before the current quotation is exported or replaced.
with sidebar_documents:
    st.divider()
    if st.button("＋ New quotation", width="stretch", key="new_quotation",
                 help="Start a blank quotation. Download the current PDF or an editable backup first if you need it."):
        fresh_quote = new_quote()
        fresh_quote["seller"] = deepcopy(quote["seller"])
        replace_quote(fresh_quote)
        st.rerun()

    with st.expander("Backup & restore"):
        st.caption("Optional: download an editable backup and restore it later, including on another device. The app does not store backups for you.")
        try:
            backup = export_quote(quote)
            st.download_button(
                "Download editable backup", data=backup,
                file_name=quote_filename(quote, extension="json"), mime="application/json",
                width="stretch", on_click="ignore",
            )
        except ValueError as error:
            st.caption(f"To back up this draft, first fix: {error}")
        uploaded = st.file_uploader("Restore a quotation backup", type=["json"], accept_multiple_files=False, key="backup_upload")
        if uploaded is not None and st.button("Open backup", width="stretch"):
            try:
                restored = import_quote(uploaded.getvalue())
                replace_quote(restored)
                st.rerun()
            except (ValueError, OSError, UnicodeError) as error:
                st.error(f"This backup could not be opened: {error}")
        st.caption("Backups include customer information. Keep them in your usual secure business storage.")

