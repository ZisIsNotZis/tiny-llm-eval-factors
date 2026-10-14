#!/usr/bin/env python3
"""Check the research doc set.

Run from the repository root:

    python3 docs/check_docs.py

Each layer file in ``docs/<layer>/<layer>.yaml`` is validated against its
refinement schema ``docs/<layer>/<layer>.schema.yaml``, which is
``allOf: [{"$ref": "docs@1"}, <that layer's domain pattern>]``. The standard
``docs@1`` is resolved from ``RESEARCH_DOCS_STANDARD`` or, by default,
``/home/z/vibe/AGENTS.docs.schema.yaml``.

Beyond schema validation the checker enforces the set-level invariants:
  * fact ids are unique inside a file (duplicate YAML keys are rejected);
  * every ``from`` is file-qualified and resolves to an existing fact;
  * no two facts carry the same ``_text``;
  * no node lacks ``_text``.

Exit status is 0 on PASS and 1 on any failure, 2 if the standard is missing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"

# (layer, layer file, refinement schema). The layer name is also the
# file-qualified prefix used in `from`.
LAYERS = [
    ("pain", "pain/pain.yaml", "pain/pain.schema.yaml"),
    ("need", "need/need.yaml", "need/need.schema.yaml"),
    ("product", "product/product.yaml", "product/product.schema.yaml"),
    ("architecture", "architecture/architecture.yaml", "architecture/architecture.schema.yaml"),
    ("method", "method/method.yaml", "method/method.schema.yaml"),
    ("plan", "plan/plan.yaml", "plan/plan.schema.yaml"),
    ("result", "result/result.yaml", "result/result.schema.yaml"),
]

STANDARD_ID = "docs@1"
DEFAULT_STANDARD = "/home/z/vibe/AGENTS.docs.schema.yaml"


class DupKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys instead of keeping the last."""


def _construct_mapping(loader: DupKeyLoader, node, deep: bool = False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate fact id: {key!r}", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DupKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load_yaml(path: Path):
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=DupKeyLoader)


def main() -> int:
    errors: list[str] = []
    facts: dict[tuple[str, str], dict] = {}
    texts: dict[str, str] = {}
    counts: list[tuple[str, int]] = []
    refs_checked = 0

    std_path = Path(os.environ.get("RESEARCH_DOCS_STANDARD", DEFAULT_STANDARD))
    if not std_path.is_file():
        print(f"FAIL: the {STANDARD_ID} standard was not found at {std_path}")
        print("      set RESEARCH_DOCS_STANDARD to the standard's path")
        return 2
    standard = load_yaml(std_path)
    registry = Registry().with_resource(
        STANDARD_ID, Resource.from_contents(standard, default_specification=DRAFT202012)
    )

    for layer, yaml_rel, schema_rel in LAYERS:
        yaml_path = DOCS / yaml_rel
        schema_path = DOCS / schema_rel
        if not yaml_path.is_file():
            errors.append(f"{yaml_rel}: layer file missing")
            continue
        if not schema_path.is_file():
            errors.append(f"{yaml_rel}: refinement schema missing ({schema_rel})")
            continue
        try:
            doc = load_yaml(yaml_path)
        except yaml.YAMLError as exc:
            errors.append(f"{yaml_rel}: unreadable YAML: {exc}")
            continue
        if not isinstance(doc, dict) or not doc:
            errors.append(f"{yaml_rel}: expected a non-empty mapping of fact id to fact")
            continue

        schema = load_yaml(schema_path)
        validator = Draft202012Validator(schema, registry=registry)
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
            errors.append(f"{yaml_rel}: schema: {list(err.path)}: {err.message}")

        counts.append((layer, len(doc)))
        for fid, fact in doc.items():
            facts[(layer, fid)] = fact
            text = fact.get("_text") if isinstance(fact, dict) else None
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{yaml_rel}: fact {fid}: missing or empty _text")
                continue
            norm = " ".join(text.split())
            where = f"{layer}.{fid}"
            if norm in texts:
                errors.append(
                    f"{yaml_rel}: fact {fid}: duplicate _text (same as {texts[norm]})"
                )
            else:
                texts[norm] = where

    for (layer, fid), fact in facts.items():
        frm = fact.get("from") if isinstance(fact, dict) else None
        if frm is None:
            continue
        for ref in [r.strip() for r in str(frm).split(",") if r.strip()]:
            refs_checked += 1
            if "." not in ref:
                errors.append(f"{layer}.{fid}: from {ref!r} is not file-qualified")
                continue
            ref_file, ref_id = ref.split(".", 1)
            if (ref_file, ref_id) not in facts:
                errors.append(f"{layer}.{fid}: from {ref!r} does not resolve")

    print("docs set check")
    for layer, n in counts:
        print(f"  [ok] {layer:<12} {n:>3} facts")
    print(f"  schema validation   : {len(LAYERS)} files vs {STANDARD_ID} + refinement")
    print(f"  ids unique in file  : {'ok' if not errors else 'see errors'}")
    print(f"  from resolves       : {refs_checked} references checked")
    print(f"  _text unique        : {len(texts)} distinct texts")
    print(f"  _text present       : every node carries _text")

    if errors:
        print("\nFAIL:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
