from io import BytesIO
import re

import fitz
from pypdf import PdfReader
import pytest

from domain import new_quote, new_option, new_charge, money, calculate_option
from pdf_export import create_pdf


FEATURE_PAGE_HEADINGS = ('DG features', 'Controls & enclosure')
FEATURE_GROUPS = ('product salient features', 'engine', 'alternator', 'controller', 'acoustic enclosure')


def normalized_words(text):
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def assert_all_feature_groups(text):
    headings = {normalized_words(line) for line in text.splitlines()}
    for group in FEATURE_GROUPS:
        assert group in headings, f'Missing feature heading: {group}'


def feature_pages_of(content):
    pages = [page.extract_text() for page in PdfReader(BytesIO(content)).pages]
    specs = next(i for i, text in enumerate(pages) if 'Technical specifications' in text.splitlines())
    return pages[1:specs]


def ready_quote():
    q = new_quote()
    q.update(lead_ref='L-001', quote_number='Q-001')
    q['customer']['name'] = 'A&B <Industries>'
    q['options'][0]['unit_price'] = '385000'
    return q


def text_of(content):
    return '\n'.join(p.extract_text() for p in PdfReader(BytesIO(content)).pages)


def assert_pricing_precedes_final_terms(content, amounts, *, include_specs=True, include_features=True):
    """Equipment precedes pricing; commercial terms finish the document."""
    texts = [page.extract_text() for page in PdfReader(BytesIO(content)).pages]

    def heading_page(heading):
        return next(i for i, text in enumerate(texts) if heading in text.splitlines())

    schedule = heading_page('Price schedule')
    terms = heading_page('Commercial terms')
    assert 0 < schedule < terms
    if include_specs:
        specs = heading_page('Technical specifications')
        assert 0 < specs < schedule
        if include_features:
            assert 0 < heading_page('DG features') < specs
            assert_all_feature_groups('\n'.join(texts[1:specs]))
        else:
            assert not any(heading in text.splitlines() for heading in FEATURE_PAGE_HEADINGS for text in texts)
            assert not any(normalized_words(line) in FEATURE_GROUPS for text in texts for line in text.splitlines())
    else:
        assert not any(heading in text.splitlines() for heading in FEATURE_PAGE_HEADINGS for text in texts)
        assert not any(normalized_words(line) in FEATURE_GROUPS for text in texts for line in text.splitlines())
        assert not any('Technical specifications' in text.splitlines() for text in texts)
        assert not any('Equipment details' in text.splitlines() for text in texts)
    outside_schedule = '\n'.join(texts[:schedule] + texts[terms:])
    for amount in amounts:
        assert amount not in outside_schedule
        assert amount in '\n'.join(texts[schedule:terms])
    assert all('Price schedule' not in text.splitlines() for text in texts[terms:])
    assert not any(heading in text.splitlines() for heading in FEATURE_PAGE_HEADINGS for text in texts[schedule:])
    assert all('Technical specifications' not in text.splitlines() for text in texts[schedule:])
    return texts, schedule, terms


def engine_and_alternator_text(content):
    """Read only the feature section, so spec-table values cannot mask omissions."""
    pages = [page.extract_text() for page in PdfReader(BytesIO(content)).pages]
    start = next(i for i, text in enumerate(pages) if 'DG features' in text.splitlines())
    end = next(i for i, text in enumerate(pages) if 'Technical specifications' in text.splitlines())
    return '\n'.join(pages[start:end])


def test_single_pdf_has_escaped_customer_correct_total_and_terms():
    q = ready_quote()
    q['reference'].update(source='Telephone discussion', meeting_date='2026-10-09', previous_quote='Q-OLD R0', discussion='Meeting & revised installation <scope>.')
    o = q['options'][0]
    o.update(transport='8000', amf_mode='Included', amf_price='16500')
    e = new_charge()
    e.update(description='Installation and commissioning', unit_price='25000')
    o['others'].append(e)
    content = create_pdf(q)
    text = text_of(content)
    for expected in ('A&B <Industries>', '5,12,710.00', 'Installation and commissioning', 'Q-OLD R0', '09 Oct 2026', 'Meeting & revised installation <scope>', 'Cancellation charges'):
        assert expected in text
    pages, schedule, terms = assert_pricing_precedes_final_terms(content, ['5,12,710.00', '4,34,500.00', '78,210.00', '3,85,000.00'])
    assert len(pages) == 6
    assert schedule == len(pages) - 2
    assert terms == len(pages) - 1
    assert '5,12,710.00' in pages[-2]
    assert 'Commercial terms' in pages[-1]
    assert 'YOUR QUOTATION TOTAL' not in pages[0]


@pytest.mark.parametrize('mode', ['alternatives', 'combined'])
def test_customer_twin_layout_has_no_orphan_pages(mode):
    q = ready_quote()
    q['mode'] = mode
    q['options'] = [new_option('400 KVA (200 x 2)'), new_option('500 KVA (250 x 2)')]
    for o in q['options']:
        o.update(unit_price='4500000', transport='25000')
    q['options'][1].update(amf_mode='Optional', amf_price='80000')
    content = create_pdf(q)
    amounts = ['53,39,500.00', '94,400.00']
    if mode == 'combined':
        amounts.append('1,06,79,000.00')
    pages, schedule, terms = assert_pricing_precedes_final_terms(content, amounts)
    assert len(pages) == 6
    specs = next(i for i, text in enumerate(pages) if 'Technical specifications' in text.splitlines())
    assert 'DG features' in '\n'.join(pages[1:specs])
    assert 'MT500DR' in pages[specs]
    assert 'Source:' in '\n'.join(pages[specs:schedule])
    assert 'Commercial terms' in pages[-1]
    assert schedule == len(pages) - 2
    assert terms == len(pages) - 1
    assert all(amount in pages[-2] for amount in amounts)


def test_long_customer_details_keep_short_offer_and_total_together():
    q = ready_quote()
    q['customer']['address'] = 'Customer address with site instructions.\n' * 11
    content = create_pdf(q)
    pages, _, terms = assert_pricing_precedes_final_terms(content, ['4,54,300.00'])
    priced_page = next(text for text in pages if 'YOUR QUOTATION TOTAL' in text)
    assert 'Unit rate' in priced_page
    assert '4,54,300.00' in priced_page
    assert '4,54,300.00' in pages[terms - 1]
    assert 'Commercial terms' in pages[-1]


def test_three_line_formal_recipient_address_is_complete_on_cover_and_schedule():
    q = ready_quote()
    q['customer']['name'] = 'The Managing Director'
    address_lines = [
        'Example Technology Corporation Limited (ETC)',
        'Projects Division,',
        'Technology Hub, 3rd floor, Business Park, Example City - 400001',
    ]
    q['customer']['address'] = '\n'.join(address_lines)
    q['options'] = [new_option('500 KVA (250 x 2)')]
    q['options'][0].update(unit_price='3925000', transport='45000')
    content = create_pdf(q)
    pages, schedule, terms = assert_pricing_precedes_final_terms(content, ['46,84,600.00'])
    for line in [q['customer']['name'], *address_lines]:
        assert line in pages[0]
        # The narrower schedule recipient block may wrap individual lines.
        assert normalized_words(line) in normalized_words(pages[schedule])
    assert schedule == len(pages) - 2
    assert terms == len(pages) - 1
    doc = fitz.open(stream=content, filetype='pdf')
    for page in doc:
        for x0, y0, x1, y1, word, *_ in page.get_text('words'):
            assert 30 <= x0 <= x1 <= page.rect.width - 30, (word, x0, x1)
            assert 15 <= y0 <= y1 <= page.rect.height - 15, (word, y0, y1)


def test_alternatives_do_not_show_combined_total_and_twin_specs_present():
    q = ready_quote()
    q['options'] = [new_option('400 KVA (200 x 2)'), new_option('500 KVA (250 x 2)')]
    for o in q['options']:
        o['unit_price'] = '1000000'
    content = create_pdf(q)
    pages, _, _ = assert_pricing_precedes_final_terms(content, ['11,80,000.00'])
    text = '\n'.join(pages)
    assert '23,60,000.00' not in text
    assert '11,80,000.00' in text
    assert 'MT500DR' in text
    assert 'To be confirmed with supplier' in text
    assert '780 L' in text
    assert '11,80,000.00' in pages[-2]
    q['mode'] = 'combined'
    combined_pages, _, _ = assert_pricing_precedes_final_terms(create_pdf(q), ['11,80,000.00', '23,60,000.00'])
    combined = '\n'.join(combined_pages)
    assert 'Combined order total' in combined
    assert '23,60,000.00' in combined_pages[-2]
    assert 'Commercial terms' in combined_pages[-1]


def test_optional_amf_excluded():
    q = ready_quote()
    q['options'][0].update(amf_mode='Optional', amf_price='10000')
    pages, _, _ = assert_pricing_precedes_final_terms(create_pdf(q), ['4,54,300.00', '11,800.00'])
    text = '\n'.join(pages)
    assert '4,54,300.00' in text
    assert '11,800.00' in text
    assert 'Optional' in text
    assert '4,66,100.00' not in text
    assert '4,54,300.00' in pages[-2]
    assert '11,800.00' in pages[-2]


@pytest.mark.parametrize('mode', ['alternatives', 'combined'])
def test_omitting_specs_skips_features_and_keeps_pricing_before_final_terms(mode):
    q = ready_quote()
    q.update(include_specs=False, mode=mode)
    q['options'] = [new_option('400 KVA (200 x 2)'), new_option('500 KVA (250 x 2)')]
    for option in q['options']:
        option['unit_price'] = '1000000'
    amounts = ['11,80,000.00']
    if mode == 'combined':
        amounts.append('23,60,000.00')
    pages, schedule, terms = assert_pricing_precedes_final_terms(create_pdf(q), amounts, include_specs=False)
    assert len(pages) == 3
    assert 'Price schedule' in pages[1]
    assert 'Commercial terms' in pages[-1]
    assert schedule == len(pages) - 2
    assert terms == len(pages) - 1
    assert all(amount in pages[-2] for amount in amounts)
    assert 'MT500DR' not in '\n'.join(pages)


def test_legacy_single_phase_features_restore_descriptions_without_three_phase_claims():
    q = ready_quote()
    q['options'] = [new_option('58.5 KVA')]
    q['options'][0].update(unit_price='385000', phase='Single Phase')
    content = create_pdf(q)
    assert_pricing_precedes_final_terms(content, ['4,54,300.00'])
    feature_text = engine_and_alternator_text(content)
    normalized = re.sub(r'[^a-z0-9]+', ' ', feature_text.lower())
    for description in ('liquid cooled', 'dry air cleaner', 'brushless', 'revolving field', 'self excited', 'h class'):
        assert description in normalized
    assert 'Single Phase' in feature_text
    assert 'V4355G2' in text_of(content)
    assert not re.search(r'\b415\s*v\b', feature_text, re.IGNORECASE)
    assert not re.search(r'\b10\s*%', feature_text)


def test_legacy_booklet_restores_salient_features_controller_and_acoustic_enclosure():
    content = create_pdf(ready_quote())
    feature_text = '\n'.join(feature_pages_of(content))
    assert_all_feature_groups(feature_text)
    normalized = normalized_words(feature_text)
    # These are substantive functions from the earlier quotation, not merely
    # headings that could remain while their descriptive content disappears.
    for function in ('gc111x', 'amf', 'manual', 'remote', 'oil pressure', 'coolant', 'overload', 'load imbalance', 'maintenance', 'usb', 'rs485', 'can'):
        assert re.search(r'\b' + re.escape(function) + r'\b', normalized), function
    assert 'powder' in normalized
    assert 'fuel filling' in normalized
    assert 'service' in normalized


def test_500_twin_features_use_brochure_electronic_engine_and_24v_starting():
    q = ready_quote()
    q['options'] = [new_option('500 KVA (250 x 2)')]
    q['options'][0]['unit_price'] = '1000000'
    content = create_pdf(q)
    assert_pricing_precedes_final_terms(content, ['11,80,000.00'])
    assert_all_feature_groups('\n'.join(feature_pages_of(content)))
    feature_text = engine_and_alternator_text(content)
    normalized = re.sub(r'[^a-z0-9]+', ' ', feature_text.lower())
    assert 'electronic' in normalized
    assert 'h class' in normalized
    assert 'brochure' in normalized
    assert re.search(r'\b24\s*v\b', feature_text, re.IGNORECASE)
    assert not re.search(r'\b12\s*v\b', feature_text, re.IGNORECASE)


def test_mixed_legacy_and_twin_options_keep_feature_profiles_separate():
    q = ready_quote()
    q['options'] = [new_option('58.5 KVA'), new_option('500 KVA (250 x 2)')]
    q['options'][0]['phase'] = 'Single Phase'
    for option in q['options']:
        option['unit_price'] = '1000000'
    content = create_pdf(q)
    pages, _, _ = assert_pricing_precedes_final_terms(content, ['11,80,000.00'])
    specs = next(i for i, text in enumerate(pages) if 'Technical specifications' in text.splitlines())
    feature_pages = pages[1:specs]
    legacy_pages = [text for text in feature_pages if re.search(r'Applies to:\s*58\.5 kVA', text)]
    twin_pages = [text for text in feature_pages if re.search(r'Applies to:\s*500 kVA \(250 x 2\)', text)]
    assert legacy_pages and twin_pages
    legacy = '\n'.join(legacy_pages)
    twin = '\n'.join(twin_pages)
    assert_all_feature_groups(legacy)
    assert_all_feature_groups(twin)
    assert legacy != twin
    assert 'Single Phase' in legacy
    assert 'dry air cleaner' in legacy.lower()
    assert not re.search(r'\b415\s*v\b', legacy, re.IGNORECASE)
    assert not re.search(r'\b10\s*%', legacy)
    assert 'electronic' in twin.lower()
    assert re.search(r'\b24\s*v\b', twin, re.IGNORECASE)


def test_400_twin_keeps_features_pending_without_a_blank_or_borrowed_feature_page():
    q = ready_quote()
    q['options'] = [new_option('400 KVA (200 x 2)')]
    q['options'][0]['unit_price'] = '1000000'
    content = create_pdf(q)
    pages, schedule, terms = assert_pricing_precedes_final_terms(content, ['11,80,000.00'], include_features=False)
    assert len(pages) == 4
    assert schedule == len(pages) - 2
    assert terms == len(pages) - 1
    specs = next(i for i, text in enumerate(pages) if 'Technical specifications' in text.splitlines())
    feature_text = '\n'.join(pages[specs:schedule])
    normalized = re.sub(r'[^a-z0-9]+', ' ', feature_text.lower())
    assert '400' in feature_text
    assert 'confirm' in normalized
    assert 'engine' in normalized
    assert 'alternator' in normalized
    for borrowed_claim in ('liquid cooled', 'dry air cleaner', 'brushless', 'revolving field', 'self excited', 'h class', 'electronic', 'h6935g1', 'h6725g4', 'gc111x', 'rs485', 'ip23'):
        assert borrowed_claim not in normalized
    assert not re.search(r'\b(?:12|24)\s*v\b', feature_text, re.IGNORECASE)


def test_long_content_survives_pagination_and_stays_on_page():
    q = ready_quote()
    q['customer']['address'] = ('Industrial estate - address line with long details.\n' * 20) + 'END-ADDRESS'
    q['reference']['discussion'] = ('Details & revisions <requested> ' * 45) + 'END-REFERENCE'
    for i in range(18):
        e = new_charge()
        e.update(description=f'Service {i}: ' + 'Installation scope and responsibilities. ' * 12 + f' END-SERVICE-{i}', unit_price='1234.56')
        q['options'][0]['others'].append(e)
    q['terms']['additional'] = 'Final terms ' * 270 + 'END-TERMS'
    content = create_pdf(q)
    total = money(calculate_option(q['options'][0])['total'])
    pages, schedule, terms = assert_pricing_precedes_final_terms(content, [total, '3,85,000.00', '1,234.56'])
    text = '\n'.join(pages)
    for token in ['END-ADDRESS', 'END-REFERENCE', 'END-TERMS'] + [f'END-SERVICE-{i}' for i in range(18)]:
        assert token in text
    # Oversized pricing and terms may both span pages. Every priced service and
    # the exact total must precede the final commercial-terms section.
    priced_text = '\n'.join(pages[schedule:terms])
    assert 'END-TERMS' in '\n'.join(pages[terms:])
    assert 'END-SERVICE-17' in priced_text
    assert 'END-TERMS' not in priced_text
    assert total in pages[terms - 1]
    assert len(pages[schedule:terms]) > 1
    assert len(pages[terms:]) > 1
    doc = fitz.open(stream=content, filetype='pdf')
    assert len(doc) >= 5
    for page in doc:
        assert page.get_text().strip()
        for x0, y0, x1, y1, word, *_ in page.get_text('words'):
            assert 30 <= x0 <= x1 <= page.rect.width - 30, (word, x0, x1)
            assert 15 <= y0 <= y1 <= page.rect.height - 15, (word, y0, y1)


def test_pdf_rejects_invalid_quote():
    with pytest.raises(ValueError):
        create_pdf(new_quote())
