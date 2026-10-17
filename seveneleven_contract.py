"""Offline admission of observed Seven-Eleven third-party JSON responses.

This module never calls a network, writes stock state, or sends notifications.
Passing this gate establishes consistency of a supplied snapshot, not physical stock.
"""
import re

BARCODE = '8800286275732'
PRODUCT = '비젼)포켓몬확장팩(30주년)_H'
PREFIXES = {
    'namwon': ('전북특별자치도 남원시 ', '전라북도 남원시 ', '전북 남원시 '),
    'asan': ('충청남도 아산시 ', '충남 아산시 '),
    'jeonju': ('전북특별자치도 전주시 ', '전라북도 전주시 ', '전북 전주시 '),
}


class UnverifiedSnapshot(ValueError):
    pass


def text(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def in_region(address, region):
    return any(text(address).startswith(p) for p in PREFIXES[region])


def identity(row):
    name = text(row.get('storeName'))
    address = text(row.get('address'))
    for alias, canonical in (
        ('전북특별자치도 ', '전라북도 '), ('전북 ', '전라북도 '),
        ('충남 ', '충청남도 '),
    ):
        if address.startswith(alias):
            address = canonical + address[len(alias):]
    return name, address


def envelope(payload):
    if not isinstance(payload, dict) or payload.get('success') is not True:
        raise UnverifiedSnapshot('API_FAILURE')
    if payload.get('error') or payload.get('isError'):
        raise UnverifiedSnapshot('API_ERROR_ENVELOPE')
    data = payload.get('data')
    if not isinstance(data, dict):
        raise UnverifiedSnapshot('INVALID_DATA')
    return data


def rows_complete(rows, total):
    if not isinstance(rows, list) or type(total) is not int or total < 0:
        raise UnverifiedSnapshot('MISSING_ROWS_OR_TOTAL')
    if len(rows) != total:
        raise UnverifiedSnapshot('INCOMPLETE_PAGE')


def code_of(row):
    code = row.get('storeCode')
    if not isinstance(code, str) or not re.fullmatch(r'[0-9]+', code):
        raise UnverifiedSnapshot('INVALID_STORE_CODE')
    if not all(identity(row)):
        raise UnverifiedSnapshot('MISSING_IDENTITY')
    return code


def classify_snapshot(directory, inventory, region):
    if region not in PREFIXES:
        raise UnverifiedSnapshot('UNSUPPORTED_REGION')
    data = envelope(directory)
    stores = data.get('stores')
    rows_complete(stores, data.get('totalCount'))
    registered = {}
    for row in stores:
        if not isinstance(row, dict):
            raise UnverifiedSnapshot('INVALID_DIRECTORY_ROW')
        code = code_of(row)
        if not in_region(row['address'], region):
            continue
        if code in registered:
            raise UnverifiedSnapshot('DUPLICATE_DIRECTORY_CODE')
        registered[code] = row
    if not registered:
        raise UnverifiedSnapshot('NO_VERIFIED_REGION_STORES')

    data = envelope(inventory)
    product = data.get('product')
    if not isinstance(product, dict) or str(product.get('itemCode')) != BARCODE:
        raise UnverifiedSnapshot('PRODUCT_CODE_MISMATCH')
    if text(product.get('itemName')) != PRODUCT:
        raise UnverifiedSnapshot('PRODUCT_NAME_MISMATCH')
    if data.get('stockAvailable') is not True or data.get('stockError'):
        raise UnverifiedSnapshot('STOCK_UNAVAILABLE')
    block = data.get('inventory')
    if not isinstance(block, dict):
        raise UnverifiedSnapshot('MISSING_INVENTORY')
    rows = block.get('stores')
    rows_complete(rows, block.get('totalStoreCount'))
    observed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise UnverifiedSnapshot('INVALID_INVENTORY_ROW')
        code = code_of(row)
        if not in_region(row['address'], region):
            continue
        if code in observed:
            raise UnverifiedSnapshot('DUPLICATE_INVENTORY_CODE')
        if code not in registered or identity(row) != identity(registered[code]):
            raise UnverifiedSnapshot('STORE_IDENTITY_MISMATCH')
        observed[code] = row

    result = {}
    for code, store in registered.items():
        row = observed.get(code, {})
        qty = row.get('stockQuantity')
        valid = type(qty) is int and qty >= 0 and store.get('closeYn') == 'N'
        result[code] = {
            'name': store['storeName'], 'address': store['address'],
            'quantity': qty if valid else None,
            'status': 'OK' if valid else 'UNKNOWN',
        }
    return result
