import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "7.26.0"
sys.path.insert(0, str(ROOT.parent / "scripts"))
from openapi_generator import bootstrap


def name(value):
    return value.replace("_", "")


def filename(value):
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name(value))
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()


def annotation(schema, request=False, refs=None):
    if "$ref" in schema:
        value = schema["$ref"].split("/")[-1]
        if refs is not None:
            refs.add(value)
        return name(value)
    if "anyOf" in schema:
        return " | ".join(dict.fromkeys(annotation(s, request, refs) for s in schema["anyOf"]))
    if "allOf" in schema:
        return annotation(schema["allOf"][0], request, refs)
    if request and "enum" in schema:
        return "Literal[" + ", ".join(repr(x) for x in schema["enum"]) + "]"
    kind = schema.get("type", "object")
    result = {"null": "None", "string": "StrictStr", "integer": "StrictInt", "boolean": "StrictBool", "number": "Decimal", "object": "dict[str, Any]"}.get(kind)
    if kind == "array":
        result = f"list[{annotation(schema['items'], request, refs)}]"
    if schema.get("format") in ("uuid", "date-time", "date"):
        result = {"uuid": "UUID", "date-time": "datetime", "date": "date"}[schema["format"]]
    if result is None:
        raise ValueError(f"Unsupported schema type: {kind!r}")
    constraints = {"maxLength": "max_length", "minLength": "min_length", "maxItems": "max_length", "minimum": "ge", "maximum": "le", "pattern": "pattern"}
    values = [f"{target}={schema[source]!r}" for source, target in constraints.items() if source in schema]
    return f"Annotated[{result}, Field({', '.join(values)})]" if values else result


def render_spec(spec):
    schemas = spec["components"]["schemas"]
    requests = {o["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1] for item in spec["paths"].values() for o in item.values() if isinstance(o, dict) and "requestBody" in o}
    for key, schema in schemas.items():
        refs = set()
        if schema.get("enum"):
            lines = [f"{name(key)} = str"]
        else:
            req = key in requests
            lines = [f"class {name(key)}(BaseModel):", f"    model_config = ConfigDict(extra={'forbid' if req else 'allow'!r}, validate_assignment=True)"]
            invalid_nulls = []
            for field, prop in schema.get("properties", {}).items():
                typ = "SecretStr | None" if field == "password" else annotation(prop, req, refs)
                optional = field not in schema.get("required", [])
                if optional and "None" not in typ:
                    invalid_nulls.append(field)
                lines.append(f"    {field}: {typ}" + (" = None" if optional else ""))
            if invalid_nulls:
                lines += ["", "    @model_validator(mode='before')", "    @classmethod", "    def reject_null(cls, value):", "        if isinstance(value, dict):", f"            for key in {invalid_nulls!r}:", "                if key in value and value[key] is None:", "                    raise ValueError(f'{key} cannot be null')", "        return value"]
        schema["x-arct-body"] = "\n".join(lines)
        schema["x-arct-imports"] = [f"from arct._generated.models.{filename(ref)} import {name(ref)}" for ref in sorted(refs) if ref != key]
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if "operationId" not in op:
                continue
            op["tags"] = ["ssh_keys" if op["operationId"].startswith("ssh_keys_") else op["operationId"].split("_", 1)[0]]
            action = op["operationId"].split("_", 1)[1]
            if op["operationId"].startswith("ssh_keys_"):
                action = op["operationId"][9:]
            if action == "list":
                action = "list_page"
            op["x-arct-name"] = action
            return_types = []
            for code, response in op["responses"].items():
                if str(code).startswith("2"):
                    schema = response.get("content", {}).get("application/json", {}).get("schema")
                    return_types.append(name(schema["$ref"].split("/")[-1]) if schema else "None")
            op["x-arct-return-type"] = " | ".join(sorted(dict.fromkeys(return_types), key=lambda value: value == "None"))
            params = op.get("parameters", [])
            path_params = [p for p in params if p["in"] == "path"]
            args = [f"{p['name']}: UUID | str" for p in path_params]
            keywords = []
            for p in params:
                if p["in"] == "query":
                    keywords.append(f"{p['name']}: {annotation(p['schema'], True)} | Unset = UNSET")
            body_ref = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("$ref")
            if body_ref:
                body_schema = schemas[body_ref.split("/")[-1]]
                for field, prop in body_schema["properties"].items():
                    typ = annotation(prop, True).replace("UUID", "UUID | str")
                    optional = field not in body_schema.get("required", [])
                    keywords.append(f"{field}: {typ}" + (" | Unset = UNSET" if optional else ""))
            signature = ([", ".join(args)] if args else []) + (["*, " + ", ".join(keywords)] if keywords else [])
            op["x-arct-signature"] = ", " + ", ".join(signature) if signature else ""
            op["x-arct-path"] = 'f"' + path + '"'
            prep = [f"        {p['name']} = UUID(str({p['name']}))" for p in path_params]
            query = ", ".join(repr(p["name"]) + ": " + p["name"] for p in params if p["in"] == "query")
            prep.append(f"        query = {{k: v for k, v in {{{query}}}.items() if v is not UNSET and v is not None}}")
            for p in params:
                if p["in"] == "query":
                    typ = annotation(p["schema"], True)
                    prep.append(f"        if {p['name']} is not UNSET and {p['name']} is not None:")
                    prep.append(f"            query[{p['name']!r}] = TypeAdapter({typ}).validate_python({p['name']})")
            if body_ref:
                body_type = name(body_ref.split("/")[-1])
                fields = ", ".join(repr(k) + ": " + k for k in body_schema["properties"])
                prep.append(f"        body = {body_type}.model_validate({{k: v for k, v in {{{fields}}}.items() if v is not UNSET}}).model_dump(exclude_unset=True, mode='python')")
            else:
                prep.append("        body = None")
            op["x-arct-prepare"] = "\n".join(prep)
    return spec


def generate(check=False):
    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        spec = render_spec(json.loads((ROOT.parent / "api/openapi.json").read_text()))
        (tmp / "input.json").write_text(json.dumps(spec))
        subprocess.run(["java", "-jar", str(bootstrap()), "generate", "-i", str(tmp / "input.json"), "-g", "python", "-t", str(ROOT / "templates"), "-o", str(tmp / "out"), "--global-property", "apis,models,apiDocs=false,modelDocs=false,apiTests=false,modelTests=false", "--additional-properties", "packageName=arct._generated,library=httpx,mapNumberTo=Decimal,generateSourceCodeOnly=true,hideGenerationTimestamp=true,disallowAdditionalPropertiesIfNotPresent=false"], check=True, stdout=subprocess.DEVNULL)
        source = tmp / "out/arct/_generated"
        for section in ("models", "api"):
            files = sorted((source / section).glob("*.py"))
            init = "\n".join(f"from .{f.stem} import {m.group(1)}" for f in files for m in re.finditer(r"^class (\w+)\(", f.read_text(), re.M))
            if section == "models":
                init += "\n" + "\n".join(f"from .{f.stem} import {m.group(1)}" for f in files for m in re.finditer(r"^(\w+) = str", f.read_text(), re.M))
            (source / section / "__init__.py").write_text(init + "\n")
        (source / "__init__.py").write_text("")
        for path in source.rglob("*.py"):
            content = path.read_text().rstrip()
            path.write_text(content + "\n" if content else "", newline="\n")
        target = ROOT / "src/arct/_generated"
        if check:
            actual = {str(f.relative_to(target)): f.read_bytes() for f in target.rglob("*.py")}
            expected = {str(f.relative_to(source)): f.read_bytes() for f in source.rglob("*.py")}
            if actual != expected:
                raise SystemExit("Generated code is out of date")
        else:
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(source, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    generate(parser.parse_args().check)
