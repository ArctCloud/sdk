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
    assert len(ids) == 25 and len(set(ids)) == len(ids), 'Review endpoint coverage.'
    assert spec['paths']['/datacenters']['get']['operationId'] == 'datacenters_list'
    for path in ('/servers', '/plans', '/images'):
        assert {'location', 'datacenter'} <= {param['name'] for param in spec['paths'][path]['get']['parameters']}
    create = spec['components']['schemas']['CreateServerRequest']
    assert create['additionalProperties'] is False
    assert create['required'] == ['hostname', 'plan', 'image_id']
    assert create['properties']['location']['deprecated'] is True
    assert create['properties']['datacenter']['pattern'] == '^[A-Za-z]{2,5}[0-9]{1,2}$'

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
    errors = {(row['status'], row['body']['error']['code']) for row in fixtures['documented_errors']}
    assert len(fixtures['documented_errors']) == len(errors) == 49
    assert {(400, 'datacenter_unavailable'), (422, 'datacenter_mismatch')} <= errors
    assert fixtures['create_datacenter_request']['datacenter'] == 'ams2'
    assert fixtures['create_datacenter']['server']['datacenter'] == 'ams2'
    assert fixtures['server_datacenter_null']['datacenter'] is None
    assert 'datacenter' not in fixtures['server_datacenter_absent']
    print('Contract valid: 25 operations, resolved references, 49 error fixtures.')


if __name__ == '__main__':
    try:
        check()
    except (AssertionError, KeyError, ValueError) as error:
        sys.exit(str(error))
