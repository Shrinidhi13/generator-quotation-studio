"""Business-rule checks with independently stated expected quotation amounts."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalog import CATALOG
from domain import (
    calculate_option, money, new_charge, new_option, new_quote,
    quote_filename, quote_totals, revise_quote, validate_quote, validate_structure,
)


def ready_quote():
    quote = new_quote()
    quote.update(lead_ref='LEAD-42', quote_number='TEM/2026/42')
    quote['customer']['name'] = 'Example Engineering'
    quote['options'][0]['unit_price'] = '385000'
    return quote


def test_known_quote_equipment_transport_amf_and_installation():
    option = new_option('125 KVA')
    option.update(unit_price='385000', transport='8000', amf_mode='Included', amf_price='16500')
    option['others'] = [dict(new_charge(), description='Installation', unit_price='25000')]
    total = calculate_option(option)
    assert total['subtotal'] == Decimal('434500.00')
    assert total['tax'] == Decimal('78210.00')
    assert total['total'] == Decimal('512710.00')
    assert money(total['total']) == '5,12,710.00'
    assert total['optional_total'] == Decimal('0.00')


def test_quantities_apply_to_equipment_panels_and_extras_but_transport_is_lump_sum():
    option = new_option()
    option.update(unit_price='100000', quantity=2, transport='1000',
                  amf_mode='Included', amf_price='5000', amf_quantity=2)
    option['others'] = [dict(new_charge(), description='Cable run', quantity=3, unit_price='2000')]
    total = calculate_option(option)
    assert total['subtotal'] == Decimal('217000.00')
    assert total['tax'] == Decimal('39060.00')
    assert total['total'] == Decimal('256060.00')


def test_optional_panel_and_extra_are_priced_separately_with_their_taxes():
    option = new_option()
    option.update(unit_price='100000', amf_mode='Optional', amf_price='5000', amf_quantity=2)
    option['others'] = [dict(new_charge(), description='Optional commissioning',
                             unit_price='2000', gst_rate='5', optional=True)]
    total = calculate_option(option)
    assert total['subtotal'] == Decimal('100000.00')
    assert total['tax'] == Decimal('18000.00')
    assert total['total'] == Decimal('118000.00')
    assert total['optional_total'] == Decimal('13900.00')
    assert len([row for row in total['rows'] if row['optional']]) == 2


@pytest.mark.parametrize('mode', ['alternatives', 'combined'])
def test_per_option_totals_do_not_implicitly_add_different_capacity_offers(mode):
    quote = ready_quote()
    quote['mode'] = mode
    quote['options'] = [dict(new_option('400 KVA (200 x 2)'), unit_price='100000'),
                        dict(new_option('500 KVA (250 x 2)'), unit_price='200000')]
    before = deepcopy(quote)
    totals = quote_totals(quote)
    assert isinstance(totals, list)
    assert [result['total'] for result in totals] == [Decimal('118000.00'), Decimal('236000.00')]
    assert quote == before


def test_flat_equipment_discount_applies_once_before_equipment_tax():
    option = new_option()
    option.update(quantity=2, unit_price='1000', discount='100', transport='100')
    total = calculate_option(option)
    assert total['rows'][0]['base'] == Decimal('1900.00')
    assert total['rows'][0]['tax'] == Decimal('342.00')
    assert '100.00' in total['rows'][0]['description']
    assert total['total'] == Decimal('2360.00')


def test_half_up_rounding_is_applied_to_money_and_each_tax_line():
    option = new_option()
    option.update(unit_price='0.245', gst_rate='10')
    option['others'] = [dict(new_charge(), description='Second tiny line', unit_price='0.25', gst_rate='10')]
    total = calculate_option(option)
    assert [row['base'] for row in total['rows']] == [Decimal('0.25'), Decimal('0.25')]
    assert [row['tax'] for row in total['rows']] == [Decimal('0.03'), Decimal('0.03')]
    assert total['total'] == Decimal('0.56')
    assert money('1.005') == '1.01'
    assert money('-1.005') == '-1.01'


@pytest.mark.parametrize('field,value', [
    ('unit_price', 'NaN'), ('unit_price', 'Infinity'), ('transport', '-Infinity'),
    ('discount', 'NaN'), ('amf_price', True), ('gst_rate', 'Infinity'),
    ('transport_gst', '-1'), ('amf_gst', '100.01'), ('quantity', 0),
    ('quantity', 1.5), ('quantity', True), ('quantity', 1001), ('amf_quantity', '2'),
    ('unit_price', '-0.01'), ('unit_price', '10000000000'),
])
def test_invalid_financial_values_cannot_enter_saved_or_generated_quotes(field, value):
    quote = ready_quote()
    quote['options'][0][field] = value
    with pytest.raises(ValueError):
        validate_structure(quote)
    assert validate_quote(quote)


def test_discount_cannot_exceed_equipment_but_can_equal_it():
    quote = ready_quote()
    quote['options'][0].update(unit_price='100', discount='100.01')
    with pytest.raises(ValueError, match='discount|Discount'):
        validate_structure(quote)
    with pytest.raises(ValueError, match='discount|Discount'):
        calculate_option(quote['options'][0])
    quote['options'][0]['discount'] = '100'
    assert calculate_option(quote['options'][0])['total'] == Decimal('0.00')


def test_empty_draft_can_be_saved_but_cannot_be_generated():
    quote = new_quote()
    validate_structure(quote)
    errors = validate_quote(quote)
    assert any('Customer name' in error for error in errors)
    assert any('Quotation number' in error for error in errors)
    assert any('Lead reference' in error for error in errors)
    assert any('price' in error for error in errors)
    assert validate_quote(ready_quote()) == []


def test_boolean_is_not_a_valid_schema_version():
    quote = new_quote()
    quote['schema_version'] = True
    with pytest.raises(ValueError):
        validate_structure(quote)


def test_revision_limit_rejects_operation_instead_of_returning_unsavable_quote():
    quote = ready_quote()
    quote['revision'] = 9999
    original = deepcopy(quote)
    with pytest.raises(ValueError):
        revise_quote(quote)
    assert quote == original


@pytest.mark.parametrize('mutation', [
    lambda q: q['options'].append(deepcopy(q['options'][0])),
    lambda q: q['options'][0].update(capacity='Imaginary 999 kVA'),
    lambda q: q['options'][0].update(capacity='500 KVA (250 x 2)', phase='Single Phase'),
    lambda q: q.update(options=[]),
    lambda q: q.update(date='2026-02-30'),
    lambda q: q['reference'].update(meeting_date='10/10/2026'),
    lambda q: q['customer'].update(name='Hidden\x00control'),
    lambda q: q['options'][0].update(others=[dict(new_charge(), optional='false')]),
])
def test_malformed_or_unsupported_quote_data_is_rejected(mutation):
    quote = ready_quote()
    mutation(quote)
    with pytest.raises(ValueError):
        validate_structure(quote)


def test_revision_is_independent_and_retains_previous_quote_reference(monkeypatch):
    quote = ready_quote()
    quote.update(date='2026-09-20', revision=2)
    quote['reference'].update(source='Meeting', meeting_date='2026-09-19', discussion='Discussed site access')
    quote['options'][0]['others'] = [dict(new_charge(), description='Installation', unit_price='5000')]
    original = deepcopy(quote)
    monkeypatch.setattr('domain.today', lambda: '2026-10-10')
    revised = revise_quote(quote)
    assert revised['id'] != quote['id']
    assert revised['revision'] == 3
    assert revised['date'] == '2026-10-10'
    assert revised['reference']['previous_quote'] == 'TEM/2026/42 / R02 dated 2026-09-20'
    assert revised['reference']['discussion'] == 'Discussed site access'
    revised['options'][0]['others'][0]['unit_price'] = '9000'
    revised['customer']['name'] = 'Changed'
    assert quote == original


@pytest.mark.parametrize('name', ['../../quote', '..\\..\\quote', 'C:\\private\\quote',
                                 'Customer/Offer: 2026?*', '....', ''] )
def test_download_filename_has_no_directory_components(name):
    quote = ready_quote()
    quote['quote_number'] = name
    result = quote_filename(quote)
    assert '/' not in result and '\\' not in result and ':' not in result
    assert not result.startswith('.')
    assert result.endswith('-R00.pdf')


def test_twin_catalog_preserves_evidence_and_does_not_invent_400_specs():
    four = CATALOG['400 KVA (200 x 2)']
    five = CATALOG['500 KVA (250 x 2)']
    assert four['twin'] and not four['verified']
    assert four['model'] is None and four['dimensions'] is None and four['tank'] is None
    assert 'confirm' in four['spec_note'].lower()
    assert five['verified'] and five['twin']
    assert (five['kva'], five['kwe'], five['model'], five['tank']) == (500, 400, 'MT500DR', 780)
    assert five['dimensions'] == '8800 x 1600 x 1975'
    assert 'approximate' in five['spec_note'].lower()
