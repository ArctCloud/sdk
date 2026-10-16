.PHONY: bootstrap install contract generate generate-check test build check

bootstrap:
	python3 scripts/openapi_generator.py --download-only

install:
	cd python && uv sync --extra test
	cd typescript && npm ci
	cd go && go mod download

contract:
	python3 scripts/check_contract.py

generate: bootstrap
	python3 scripts/prepare_openapi.py
	python3 python/scripts/generate.py
	python3 go/scripts/generate.py
	cd typescript && npm run generate

generate-check: bootstrap contract
	python3 python/scripts/generate.py --check
	python3 go/scripts/generate.py --check
	cd typescript && npm run generate:check

test:
	python3 -m unittest discover -s scripts -p '*_test.py'
	cd python && uv run --extra test pytest -q
	cd typescript && npm test
	cd go && go test -race ./...
	cd go && go vet ./...

build:
	mkdir -p build
	cd python && uv build
	cd typescript && npm pack --pack-destination ../build
	cd go && go build -trimpath -o ../build/arct ./cmd/arct

check: generate-check test
