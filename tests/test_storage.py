"""Local draft and import boundary tests using isolated temporary directories."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain import new_quote, revise_quote
import storage


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    data = tmp_path / 'drafts'
    monkeypatch.setattr(storage, 'DATA_DIR', data)
    return data


def test_incomplete_draft_save_load_and_utf8_export_round_trip(isolated_data):
    quote = new_quote()
    quote['customer']['name'] = 'प्रगती Engineering & Sons'
    quote['reference']['discussion'] = 'Telephone discussion\nReview installation.'
    before = deepcopy(quote)
    path = storage.save_quote(quote)
    assert path.parent == isolated_data
    assert path.name == quote['id'] + '.json'
    assert storage.load_quote(quote['id']) == before
    backup = storage.export_quote(quote)
    assert isinstance(backup, bytes)
    assert 'प्रगती' in backup.decode('utf-8')
    assert storage.import_quote(backup) == before
    assert storage.import_quote(b'\xef\xbb\xbf' + backup) == before
    assert quote == before


def test_revision_saves_new_file_without_changing_original(isolated_data):
    original = new_quote()
    original.update(lead_ref='LEAD-7', quote_number='TEM-7', date='2026-09-20')
    original_path = storage.save_quote(original)
    original_bytes = original_path.read_bytes()
    revised = revise_quote(original)
    revised['options'][0]['unit_price'] = '420000'
    revised_path = storage.save_quote(revised)
    assert revised_path != original_path
    assert original_path.read_bytes() == original_bytes
    assert storage.load_quote(original['id']) == original
    assert storage.load_quote(revised['id']) == revised
    summaries = storage.list_quotes()
    assert {q['id'] for q in summaries} == {original['id'], revised['id']}
    assert {q['revision'] for q in summaries} == {0, 1}


def test_replacing_existing_draft_is_atomic_on_write_failure(isolated_data, monkeypatch):
    quote = new_quote()
    path = storage.save_quote(quote)
    previous = path.read_bytes()
    quote['customer']['name'] = 'Later edit'
    def reject_replace(*args):
        raise OSError('Simulated disk replacement failure')
    monkeypatch.setattr(storage.os, 'replace', reject_replace)
    with pytest.raises(OSError, match='replacement failure'):
        storage.save_quote(quote)
    assert path.read_bytes() == previous
    assert list(isolated_data.glob('*.tmp')) == []


@pytest.mark.parametrize('payload', [b'', b'not JSON', b'{', b'\xff\xfe', b'[]', b'null',
                                     b'{"schema_version":2}', b'{"schema_version":1}',
                                     b' ' * 2_000_001],
                         ids=['empty', 'text', 'truncated', 'invalid-utf8', 'array', 'null',
                              'unsupported-schema', 'missing-fields', 'oversized'])
def test_malformed_and_oversized_backups_are_rejected(payload, isolated_data):
    with pytest.raises(ValueError):
        storage.import_quote(payload)
    assert not isolated_data.exists()


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', float('nan'), float('inf')])
def test_nonfinite_imported_prices_are_rejected(value):
    quote = new_quote()
    quote['options'][0]['unit_price'] = value
    payload = json.dumps(quote).encode('utf-8')
    with pytest.raises(ValueError):
        storage.import_quote(payload)


@pytest.mark.parametrize('quote_id', ['../outside', '..\\outside', '/tmp/outside',
                                     'C:\\outside', '', None, '../' + 'a' * 33])
def test_load_rejects_path_traversal_and_invalid_ids(quote_id, isolated_data):
    with pytest.raises(ValueError, match='ID'):
        storage.load_quote(quote_id)
    assert not isolated_data.exists()


def test_save_rejects_path_traversal_id_before_creating_any_files(isolated_data):
    quote = new_quote()
    quote['id'] = '../' + 'a' * 33
    with pytest.raises(ValueError):
        storage.save_quote(quote)
    assert not isolated_data.exists()


def test_invalid_draft_does_not_overwrite_previously_saved_file():
    quote = new_quote()
    path = storage.save_quote(quote)
    previous = path.read_bytes()
    quote['options'][0]['unit_price'] = 'NaN'
    with pytest.raises(ValueError):
        storage.save_quote(quote)
    assert path.read_bytes() == previous


def test_listing_ignores_corrupt_files_and_mismatched_ids(isolated_data):
    assert storage.list_quotes() == []
    quote = new_quote()
    quote['customer']['name'] = 'Valid customer'
    storage.save_quote(quote)
    (isolated_data / 'damaged.json').write_text('{bad JSON', encoding='utf-8')
    mismatch = new_quote()
    (isolated_data / ('a' * 36 + '.json')).write_bytes(storage.export_quote(mismatch))
    assert storage.list_quotes() == [dict(id=quote['id'], lead_ref=quote['lead_ref'],
                                          quote_number=quote['quote_number'], revision=0,
                                          customer_name='Valid customer', date=quote['date'])]


def test_import_is_read_only_until_saved_explicitly(isolated_data):
    quote = new_quote()
    imported = storage.import_quote(storage.export_quote(quote))
    assert imported['id'] == quote['id']
    assert not isolated_data.exists()
