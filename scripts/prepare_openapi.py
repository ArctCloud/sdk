import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(source):
    result = copy.deepcopy(source)
    for path, methods in result['paths'].items():
        parts = path.strip('/').split('/')
        resource = parts[0].replace('-', '_')
        for method, operation in methods.items():
            if method not in {'get', 'post', 'patch', 'delete', 'put'}:
                continue
            if len(parts) > 2:
                action = parts[-1].replace('-', '_')
            elif method == 'get':
                action = 'get' if len(parts) > 1 or resource == 'account' else 'list'
            else:
                action = {'post': 'create', 'patch': 'update', 'delete': 'delete', 'put': 'replace'}[method]
            operation['operationId'] = resource + '_' + action
            operation['x-arct-resource'] = resource
            operation['x-arct-action'] = action
    result['paths']['/servers/{server_id}/resize']['post']['responses']['202']['content'] = {
        'application/json': {'schema': {'$ref': '#/components/schemas/ResizeResponse'}}
    }
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = json.dumps(prepare(json.loads((ROOT / 'api/upstream-openapi.json').read_text())), indent=2) + '\n'
    target = ROOT / 'api/openapi.json'
    if args.check:
        if not target.exists() or target.read_text() != content:
            raise SystemExit('Normalized OpenAPI is out of date.')
    else:
        target.write_text(content)

