import json
import sys
from pathlib import Path

from prepare_openapi import prepare

ROOT = Path(__file__).resolve().parents[1]


def check():
    source = json.loads((ROOT / 'api/upstream-openapi.json').read_text())
    spec = json.loads((ROOT / 'api/openapi.json').read_text())
    assert spec == prepare(source), 'Run scripts/prepare_openapi.py.'
    operations = [op for item in spec['paths'].values() for method, op in item.items()
                  if method in {'get', 'post', 'put', 'patch', 'delete'}]
    ids = [op['operationId'] for op in operations]
    assert len(ids) == 22 and len(set(ids)) == len(ids), 'Review endpoint coverage.'

    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if '$ref' in value:
                ref = value['$ref']
                assert ref.startswith('#/'), f'External reference: {ref}'
                resolved = spec
                for part in ref[2:].split('/'):
                    resolved = resolved[part.replace('~1', '/').replace('~0', '~')]
            for item in value.values():
                visit(item)

    visit(spec)
    fixtures = json.loads((ROOT / 'api/test-cases.json').read_text())
    assert len(fixtures['documented_errors']) == 42
    assert len({(row['status'], row['body']['error']['code']) for row in fixtures['documented_errors']}) == 42
    print('Contract valid: 22 operations, resolved references, 42 error fixtures.')


if __name__ == '__main__':
    try:
        check()
    except (AssertionError, KeyError, ValueError) as error:
        sys.exit(str(error))
