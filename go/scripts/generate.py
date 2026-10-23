import argparse
import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGET = ROOT / 'go/internal/generated'


def compatible(value):
    if isinstance(value, list):
        return [compatible(v) for v in value]
    if not isinstance(value, dict):
        return value
    value = {k: compatible(v) for k, v in value.items()}
    if 'const' in value:
        value['enum'] = [value.pop('const')]
    if isinstance(value.get('examples'), list):
        examples = value.pop('examples')
        if examples:
            value['example'] = examples[0]
    if 'anyOf' in value:
        choices = value['anyOf']
        nonnull = [v for v in choices if v.get('type') != 'null']
        if len(nonnull) == 1 and len(nonnull) != len(choices):
            value.pop('anyOf')
            value.update(nonnull[0])
            value['nullable'] = True
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    loader = importlib.util.spec_from_file_location('arct_generator', ROOT / 'scripts/openapi_generator.py')
    bootstrap = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(bootstrap)
    jar = bootstrap.bootstrap()
    spec = compatible(json.loads((ROOT / 'api/openapi.json').read_text()))
    spec['openapi'] = '3.0.3'
    for path in spec['paths'].values():
        for operation in path.values():
            if not isinstance(operation, dict):
                continue
            if 'requestBody' in operation:
                operation['requestBody']['content']['application/json']['schema'] = {'type': 'object', 'additionalProperties': True}
            for response in operation.get('responses', {}).values():
                if 'content' in response:
                    response['content']['application/json']['schema'] = {'type': 'object', 'additionalProperties': True}
    with tempfile.TemporaryDirectory() as tmp:
        source = pathlib.Path(tmp) / 'compat.json'
        output = pathlib.Path(tmp) / 'generated'
        source.write_text(json.dumps(spec))
        subprocess.run(['java', '-jar', str(jar), 'generate', '-g', 'go', '-i', str(source), '-o', str(output),
                        '--additional-properties=packageName=generated,hideGenerationTimestamp=true,enumClassPrefix=true,disallowAdditionalPropertiesIfNotPresent=false',
                        '--global-property=apis,models,supportingFiles=client.go:configuration.go:response.go:utils.go,apiTests=false,modelTests=false,apiDocs=false,modelDocs=false'], check=True, stdout=subprocess.DEVNULL)
        for path in list(output.iterdir()):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.suffix != '.go':
                path.unlink()
        subprocess.run(['gofmt', '-w', str(output)], check=True)
        if args.check:
            expected = {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()}
            actual = {p.relative_to(TARGET): p.read_bytes() for p in TARGET.rglob('*') if p.is_file()}
            changed = sorted(str(p) for p in expected.keys() | actual.keys() if expected.get(p) != actual.get(p))
            if changed:
                raise SystemExit('Generated Go files differ: ' + ', '.join(changed))
            print('Go generation is current.')
        else:
            shutil.rmtree(TARGET, ignore_errors=True)
            shutil.copytree(output, TARGET)


if __name__ == '__main__':
    main()
