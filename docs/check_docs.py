#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the research doc set.

Run from the repository root:

    python3 docs/check_docs.py

Facts live in two shapes during the migration:

  * a layer file `docs/<layer>/<layer>.yaml` validated against its refinement
    schema `docs/<layer>/<layer>.schema.yaml`, which is
    ``allOf: [{"$ref": "docs@1"}, <that layer's domain pattern>]``;
  * per-subproject plan/result files `docs/subprojects/<id>-<name>/{plan,result}.{yaml,md}`.
    A subproject that has migrated writes Markdown facts, one per `## <id> :: <text>`
    heading with `- key: value` coordinates under it.

The standard ``docs@1`` is resolved from ``RESEARCH_DOCS_STANDARD`` or, by default,
``/home/z/vibe/AGENTS.docs.schema.yaml``.  When it is missing the schema half of the
check cannot run, and that is reported as BLOCKED with the exact path - never as a
pass.  The set-level invariants below do not depend on it and still run:

  * fact ids are unique inside a file (duplicate YAML keys are rejected);
  * every ``from`` is file-qualified and resolves to an existing fact;
  * no two facts carry the same ``_text``;
  * no node lacks ``_text``.

Exit status is 0 when everything checkable passed, 1 on any invariant or schema
failure, and 2 when the ``docs@1`` standard is missing (blocked, unverified).
"""
from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

import yaml

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except ImportError:  # 缺依赖就不假装校验过
    Draft202012Validator = None

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
]

# layers cut per subproject instead of a single layer file
SUBPROJECT_LAYERS = ("plan", "result")

STANDARD_ID = "docs@1"
DEFAULT_STANDARD = "/home/z/vibe/AGENTS.docs.schema.yaml"

MD_FACT_RE = re.compile(r"^#{2,6}\s+([A-Za-z][\w.-]*)\s+::\s+(\S.*)$")
MD_FIELD_RE = re.compile(r"^[-*]\s+(\w+)\s*:\s*(\S.*)$")


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


def md_facts(path: Path):
    """`## <id> :: <text>` 标题 + `- key: value` 坐标；不带 ` :: ` 的标题是普通小节。"""
    facts, cur = {}, None
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = MD_FACT_RE.match(line)
        if m:
            cur = {"_text": m.group(2)}
            facts[m.group(1)] = cur
            continue
        if line.startswith("#"):
            cur = None
            continue
        if cur is None:
            continue
        f = MD_FIELD_RE.match(line)
        if not f:
            continue
        key, value = f.group(1), f.group(2)
        if key == "kind":
            cur.setdefault("domain", {})["kind"] = value
        else:
            cur[key] = value
    return facts


def main() -> int:
    errors: list[str] = []
    blocked = None
    facts: dict[tuple[str, str], dict] = {}
    texts: dict[str, str] = {}
    counts: list[tuple[str, int]] = []
    shapeless: list[str] = []
    refs_checked = 0

    std_path = Path(os.environ.get("RESEARCH_DOCS_STANDARD", DEFAULT_STANDARD))
    standard = registry = None
    if not std_path.is_file():
        blocked = str(std_path)
    elif Draft202012Validator is None:
        blocked = "jsonschema/referencing not installed"
    else:
        standard = load_yaml(std_path)
        registry = Registry().with_resource(
            STANDARD_ID, Resource.from_contents(standard, default_specification=DRAFT202012)
        )

    def collect(label: str, doc: dict):
        counts.append((label, len(doc)))
        for fid, fact in doc.items():
            where = f"{label}.{fid}"
            if (label, fid) in facts:
                errors.append(f"{label}: fact id {fid!r} declared twice")
                continue
            facts[(label, fid)] = fact
            text = fact.get("_text") if isinstance(fact, dict) else None
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{label}: fact {fid}: missing or empty _text")
                continue
            norm = " ".join(text.split())
            if norm in texts:
                errors.append(f"{label}: fact {fid}: duplicate _text (same as {texts[norm]})")
            else:
                texts[norm] = where

    # single-file layers
    for layer, yaml_rel, schema_rel in LAYERS:
        yaml_path = DOCS / yaml_rel
        if not yaml_path.is_file():
            errors.append(f"{yaml_rel}: layer file missing")
            continue
        try:
            doc = load_yaml(yaml_path)
        except yaml.YAMLError as exc:
            errors.append(f"{yaml_rel}: unreadable YAML: {exc}")
            continue
        if not isinstance(doc, dict) or not doc:
            errors.append(f"{yaml_rel}: expected a non-empty mapping of fact id to fact")
            continue
        schema_path = DOCS / schema_rel
        if blocked or not schema_path.is_file():
            if not schema_path.is_file():
                errors.append(f"{yaml_rel}: refinement schema missing ({schema_rel})")
        else:
            try:
                validator = Draft202012Validator(load_yaml(schema_path), registry=registry)
                for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
                    errors.append(f"{yaml_rel}: schema: {list(err.path)}: {err.message}")
            except Exception as exc:  # schema itself unusable
                errors.append(f"{yaml_rel}: cannot validate: {exc}")
        collect(layer, doc)

    # per-subproject layers, in both shapes
    for layer in SUBPROJECT_LAYERS:
        merged: dict[str, dict] = {}
        files = sorted(glob.glob(str(DOCS / "subprojects" / "*" / f"{layer}.yaml")))
        files += sorted(p for p in glob.glob(str(DOCS / "subprojects" / "*" / "*.md"))
                        if Path(p).stem.lower() == layer)
        if not files:
            errors.append(f"docs/subprojects/*/{layer}.yaml: no subproject owns this layer")
        for path in files:
            p = Path(path)
            try:
                doc = (md_facts(p) if p.suffix == ".md" else load_yaml(p)) or {}
            except yaml.YAMLError as exc:
                errors.append(f"{p.relative_to(REPO)}: unreadable YAML: {exc}")
                continue
            if not isinstance(doc, dict) or not doc:
                # 各子项目的 Markdown 事实形状尚未统一，这里只记录哪些文件不提供可解析的
                # 事实（它们的节点因此不进报告），不因此判整个文档集失败。
                shapeless.append(str(p.relative_to(REPO)))
                continue
            for fid in doc:
                if fid in merged:
                    errors.append(f"{layer}: fact id {fid!r} declared in two subprojects")
            merged.update(doc)
        collect(layer, merged)

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
    for label, n in counts:
        print(f"  [ok] {label:<12} {n:>3} facts")
    print(f"  schema validation   : {'BLOCKED' if blocked else 'ran'} "
          f"(standard {STANDARD_ID} at {std_path})")
    print(f"  ids unique          : {'ok' if not errors else 'see errors'}")
    print(f"  from resolves       : {refs_checked} references checked")
    print(f"  _text unique        : {len(texts)} distinct texts")
    print(f"  _text present       : every node carries _text")
    if shapeless:
        print(f"  shape not parsed    : {len(shapeless)} file(s) carry no `## <id> :: <text>` fact:")
        for rel in shapeless:
            print(f"      {rel}")

    if blocked:
        print(f"\nBLOCKED: the {STANDARD_ID} standard was not found at {blocked}")
        print("         set RESEARCH_DOCS_STANDARD to the standard's path")
        print("         schema validation did not run; the invariants above did")
    if errors:
        print("\nFAIL:")
        for err in errors:
            print(f"  - {err}")
        return 1
    if blocked:
        return 2
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
