"""Safe GS25 independent configuration check. No external requests or alerts."""
import json
import sys
from pathlib import Path

CONFIG = Path(__file__).with_name('config.json')
EXPECTED = {'namwon': True, 'asan': True, 'jeonju': True, 'jeju': True}


def main():
    try:
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        assert config['provider'] == 'GS25'
        assert config['item_code'] == '8800286275732'
        assert config['item_code_verified'] is False
        regions = config['regions']
        assert {r['id']: r['enabled'] for r in regions} == EXPECTED
        assert all(isinstance(r['name'], str) and r['name'] for r in regions)
    except (OSError, ValueError, KeyError, AssertionError, TypeError) as exc:
        print('GS25_CONFIG_INVALID', type(exc).__name__)
        return 2
    print('GS25_CONFIG_VALID')
    print('GS25_REGIONS namwon=ON asan=ON jeonju=ON jeju=ON')
    print('GS25_ITEM_CODE_ASSUMED 8800286275732')
    print('GS25_PROVIDER_STATUS AUTHORIZED_STOCK_INTERFACE_NOT_CONFIGURED')
    print('GS25_STOCK_CHECKS=0 ALERTS=0 STATE_WRITES=0')
    print('GS25_MONITOR_NOT_ACTIVE: no authorized external stock interface is configured')
    return 0


if __name__ == '__main__':
    sys.exit(main())
