"""Quotation data and money rules. No UI, network or filesystem side effects."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from uuid import uuid4

from catalog import CATALOG

CENT = Decimal('0.01')
MAX_AMOUNT = Decimal('9999999999.99')


def today():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()


def new_charge():
    return dict(description='', quantity=1, unit_price='0.00', gst_rate='18', optional=False)


def new_option(capacity='125 KVA'):
    return dict(id=str(uuid4()), capacity=capacity, phase='3 Phase', quantity=1,
                unit_price='0.00', gst_rate='18', discount='0.00', transport='0.00',
                transport_gst='18', amf_mode='Not required', amf_price='0.00',
                amf_quantity=1, amf_gst='18', others=[], notes='')


def new_quote():
    return dict(schema_version=1, id=str(uuid4()), lead_ref='', quote_number='',
                revision=0, date=today(), valid_days=8, mode='alternatives', include_specs=True,
                customer=dict(name='', address='', attention='', phone='', email='', gstin=''),
                reference=dict(source='Enquiry over telephone', meeting_date='', previous_quote='', discussion=''),
                seller=dict(name='Techno Electromechs', contact='Venkatesh Bhat',
                            phone='9823012044 / 9022330752', email='techno.tems@gmail.com',
                            address='54/15 A, SHRI-NIVASA, Near Vasantrao Chougule School, Morewadi Road, Kolhapur - 416004', gstin=''),
                options=[new_option()],
                terms=dict(payment='100% advance for immediate delivery, or 30% advance with the order and the balance 70% against pro forma invoice before dispatch.',
                           delivery='2-4 weeks from receipt of order and advance, subject to availability and written confirmation.',
                           warranty='As per the applicable manufacturer warranty for the selected model, to be confirmed in the order acknowledgement.',
                           scope='Supply is limited to the equipment and services explicitly priced as included in this quotation. Optional items are excluded from the offer total unless accepted separately.',
                           exclusions='Unpriced unloading, civil foundation, earthing, power and control cabling, exhaust piping, changeover switches and installation are excluded. Statutory approvals are to the customer account. Transit insurance is excluded unless expressly included in a priced line.',
                           additional='Customer to mention GST/TAN/PAN and date on the purchase order. If delivery is deferred, a revised schedule and any price implications will be mutually agreed. Cancellation charges: 2.5% of the basic order value. Disputes are subject to arbitration under the Arbitration and Conciliation Act, 1996, at the applicable jurisdiction.'))


def decimal(value):
    if isinstance(value, bool):
        raise ValueError('Enter a valid number.')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Enter a valid number.') from None
    if not number.is_finite():
        raise ValueError('Numbers must be finite.')
    return number


def amount(value):
    n = decimal(value)
    if not 0 <= n <= MAX_AMOUNT:
        raise ValueError('Amounts must be between 0 and 9,99,99,99,999.99.')
    return n.quantize(CENT, rounding=ROUND_HALF_UP)


def tax_rate(value):
    n = decimal(value)
    if not 0 <= n <= 100:
        raise ValueError('Tax percentage must be between 0 and 100.')
    return n


def quantity(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1000:
        raise ValueError('Quantity must be a whole number from 1 to 1,000.')
    return value


def money(value):
    whole, fraction = f'{decimal(value).quantize(CENT, rounding=ROUND_HALF_UP):.2f}'.split('.')
    sign = '-' if whole.startswith('-') else ''
    whole = whole.lstrip('-')
    tail = whole[-3:]
    head = whole[:-3]
    parts = []
    while head:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return sign + ','.join(parts + [tail]) + '.' + fraction


def calculate_option(option):
    rows = []

    def row(description, count, rate, gst, optional=False, discount='0'):
        count, rate, gst = quantity(count), amount(rate), tax_rate(gst)
        base = rate * count - amount(discount)
        if base < 0:
            raise ValueError('Discount cannot exceed the equipment amount.')
        tax = (base * gst / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        rows.append(dict(description=description, quantity=count, rate=rate, base=base,
                         tax_rate=gst, tax=tax, total=base + tax, optional=optional))

    desc = f"Mahindra Powerol {option['capacity']} - {option['phase']}"
    if amount(option['discount']):
        desc += f" (equipment discount: INR {money(option['discount'])})"
    row(desc, option['quantity'], option['unit_price'], option['gst_rate'], discount=option['discount'])
    if amount(option['transport']):
        row('Transportation (per offer)', 1, option['transport'], option['transport_gst'])
    if option['amf_mode'] != 'Not required':
        row('AMF panel', option['amf_quantity'], option['amf_price'], option['amf_gst'], option['amf_mode'] == 'Optional')
    for extra in option['others']:
        row(extra['description'], extra['quantity'], extra['unit_price'], extra['gst_rate'], extra['optional'])
    included = [r for r in rows if not r['optional']]
    subtotal = sum((r['base'] for r in included), Decimal('0.00'))
    tax = sum((r['tax'] for r in included), Decimal('0.00'))
    return dict(rows=rows, subtotal=subtotal, tax=tax, total=subtotal + tax,
                optional_total=sum((r['total'] for r in rows if r['optional']), Decimal('0.00')))


def quote_totals(quote):
    return [calculate_option(o) for o in quote['options']]


def _text(value, label, limit=4000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'{label} must be text of at most {limit:,} characters.')
    # Keep supported newlines, reject hidden controls that can damage PDF layout.
    if any(ord(c) < 32 and c not in '\n\t\r' for c in value):
        raise ValueError(f'{label} contains unsupported control characters.')


def _date(value, label, optional=False):
    if optional and value == '':
        return
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(f'{label} must be a date in YYYY-MM-DD format.')
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{label} is not a valid date.') from None


def validate_structure(q):
    """Validate imports and saved drafts, including incomplete but well-formed drafts."""
    if not isinstance(q, dict) or type(q.get('schema_version')) is not int or q['schema_version'] != 1:
        raise ValueError('This is not a supported quotation backup (schema version 1).')
    try:
        template = new_quote()
        for key in template:
            if key not in q:
                raise ValueError(f'Missing quotation field: {key}.')
        if not re.fullmatch(r'[a-f0-9-]{36}', q['id']):
            raise ValueError('Invalid quotation ID.')
        for k in ('lead_ref', 'quote_number'):
            _text(q[k], k, 100)
        if type(q['revision']) is not int or not 0 <= q['revision'] <= 9999:
            raise ValueError('Invalid revision number.')
        if type(q['valid_days']) is not int or not 1 <= q['valid_days'] <= 365:
            raise ValueError('Validity must be 1-365 days.')
        _date(q['date'], 'Quotation date')
        if date.fromisoformat(q['date']).year > 9900:
            raise ValueError('Quotation date is outside the supported range.')
        if q['mode'] not in ('alternatives', 'combined') or type(q['include_specs']) is not bool:
            raise ValueError('Invalid quotation settings.')
        for group in ('customer', 'seller', 'reference', 'terms'):
            if not isinstance(q[group], dict):
                raise ValueError(f'Invalid {group} fields.')
            for k in template[group]:
                _text(q[group][k], f'{group}: {k}', 4000 if group == 'terms' else 2000)
        _date(q['reference']['meeting_date'], 'Reference date', optional=True)
        if not isinstance(q['options'], list) or not 1 <= len(q['options']) <= 20:
            raise ValueError('A quotation needs between 1 and 20 DG options.')
        seen = set()
        for i, o in enumerate(q['options'], 1):
            if not isinstance(o, dict) or any(k not in o for k in new_option()):
                raise ValueError(f'Option {i} has missing fields.')
            if not isinstance(o['id'], str) or not re.fullmatch(r'[a-f0-9-]{36}', o['id']) or o['id'] in seen:
                raise ValueError('Options need distinct valid IDs.')
            seen.add(o['id'])
            if o['capacity'] not in CATALOG:
                raise ValueError(f'Option {i}: unknown DG capacity.')
            if o['phase'] not in CATALOG[o['capacity']]['phase_options']:
                raise ValueError(f'Option {i}: unsupported phase for this capacity.')
            quantity(o['quantity'])
            quantity(o['amf_quantity'])
            for k in ('unit_price', 'discount', 'transport', 'amf_price'):
                amount(o[k])
            for k in ('gst_rate', 'transport_gst', 'amf_gst'):
                tax_rate(o[k])
            if amount(o['discount']) > amount(o['unit_price']) * o['quantity']:
                raise ValueError(f'Option {i}: discount exceeds equipment amount.')
            if o['amf_mode'] not in ('Not required', 'Included', 'Optional'):
                raise ValueError(f'Option {i}: invalid AMF choice.')
            _text(o['notes'], f'Option {i} notes', 4000)
            if not isinstance(o['others'], list) or len(o['others']) > 30:
                raise ValueError('Use at most 30 extra charges per offer.')
            for e in o['others']:
                _text(e['description'], 'Other charge description', 1000)
                quantity(e['quantity'])
                amount(e['unit_price'])
                tax_rate(e['gst_rate'])
                if type(e['optional']) is not bool:
                    raise ValueError('Invalid optional charge flag.')
    except (KeyError, TypeError) as exc:
        raise ValueError('Quotation backup has missing or invalid fields.') from exc


def validate_quote(q):
    try:
        validate_structure(q)
    except ValueError as exc:
        return [str(exc)]
    errors = []
    for value, label in ((q['lead_ref'], 'Lead reference'), (q['quote_number'], 'Quotation number'),
                         (q['customer']['name'], 'Customer name'), (q['seller']['name'], 'Seller name')):
        if not value.strip():
            errors.append(f'{label} is required.')
    email = q['customer']['email'].strip()
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        errors.append('Enter a valid customer email or leave it blank.')
    for i, o in enumerate(q['options'], 1):
        if amount(o['unit_price']) <= 0:
            errors.append(f'Option {i}: enter the price per DG system.')
        if o['amf_mode'] != 'Not required' and amount(o['amf_price']) <= 0:
            errors.append(f'Option {i}: enter the AMF price or choose Not required.')
        for e in o['others']:
            if not e['description'].strip():
                errors.append(f'Option {i}: give every Other charge a description.')
    return errors


def revise_quote(q):
    validate_structure(q)
    if q['revision'] >= 9999:
        raise ValueError('This quotation has reached the revision limit. Start a new quotation number.')
    revised = deepcopy(q)
    revised['id'] = str(uuid4())
    revised['revision'] += 1
    revised['date'] = today()
    revised['reference']['previous_quote'] = f"{q['quote_number']} / R{q['revision']:02d} dated {q['date']}"
    return revised


def quote_filename(q, extension='pdf'):
    name = re.sub(r'[^A-Za-z0-9._-]+', '-', q['quote_number'] or q['lead_ref'] or 'quotation').strip('.-')[:80] or 'quotation'
    return f"{name}-R{q['revision']:02d}.{extension}"
