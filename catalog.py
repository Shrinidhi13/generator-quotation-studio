"""A single catalog for the form and PDF. Source qualifications travel with specs."""
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / 'assets'
LEGACY = json.loads((ASSETS / 'legacy-catalog.json').read_text(encoding='utf-8'))
CATALOG = {}
for key, spec in LEGACY.items():
    kva = float(key.replace(' KVA', '').replace('*', ''))
    CATALOG[key] = dict(
        label=key.replace('KVA', 'kVA'), kva=kva, kwe=spec['kWe'], model=spec['model'],
        bhp=spec['bhp'], dimensions=spec['dim'], tank=spec['tank'],
        # Legacy app permits either phase. Preserve it without asserting unverified voltage.
        phase_options=['3 Phase', 'Single Phase'], twin=False, verified=False,
        spec_note='Legacy catalog specifications; confirm model, phase availability and current manufacturer specifications before order.'
                  + (' The asterisk is retained from the original catalog.' if '*' in key else ''),
        specs={'Power rating': f"{spec['kWe']} kWe", 'Engine model': spec['model'],
               'Engine output': f"{spec['bhp']} BHP", 'Dimensions (L x W x H)': f"{spec['dim']} mm",
               'Fuel tank': f"{spec['tank']} L"})

CATALOG['400 KVA (200 x 2)'] = dict(
    label='400 kVA (200 x 2)', kva=400, kwe=None, model=None, bhp=None, dimensions=None,
    tank=None, phase_options=['3 Phase'], twin=True, verified=False,
    spec_note='Requested 200 kVA x 2 configuration. Not covered in the supplied brochure. Technical specifications and availability to be confirmed with supplier.',
    specs={'Configuration': '200 kVA x 2 (one twin system)', 'Total requested capacity': '400 kVA',
           'Technical specifications': 'To be confirmed with supplier'})

CATALOG['500 KVA (250 x 2)'] = dict(
    label='500 kVA (250 x 2)', kva=500, kwe=400, model='MT500DR', bhp=620,
    dimensions='8800 x 1600 x 1975', tank=780, phase_options=['3 Phase'], twin=True, verified=True,
    spec_note='Source: supplied Twin DG Set 500/640 kVA brochure, pages 4 and 6. Dimensions are approximate. Confirm current availability and applicable emission certification before order.',
    specs={'Configuration': '250 kVA x 2 (one twin system)', 'Genset model': 'MT500DR',
           'Duty / power': 'Prime / 500 kVA / 400 kW', 'Output': '415 V / 3 phase / 50 Hz',
           'Current / power factor': '695 A / 0.8 lagging', 'Speed': '1500 RPM',
           'Engine model': 'Mahindra H6935G1 (electronic)', 'Rated engine output (as printed)': '620 hp',
           'Cylinders / displacement': '6 x 2 / 9.3 x 2 L', 'Fuel tank': '780 L',
           'DEF tank': '50 + 50 L', 'Starting system': '24 V',
           'Approx. dimensions (L x W x H)': '8800 x 1600 x 1975 mm'})
