#!/usr/bin/env python3
"""Archive manifest: what of the study's evidence base still exists.

Distinguishes, for every model file referenced by the DB:
  - present : resolvable on disk (regular file or valid symlink)
  - missing : referenced but gone

and inventories the raw eval artifacts under evalplus_results/.

Outputs archive_manifest.json + ARCHIVE_MANIFEST.md
"""
import json
import os
import sqlite3

HF = "/home/z/hf"
ART = "/home/z/hf/research/evalplus_results"


def db_models():
    db = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)
    return sorted({r[0] for r in db.execute("SELECT DISTINCT model FROM experiments")})


def resolve(name):
    p = os.path.join(HF, name)
    if os.path.exists(p):
        return p
    # try a glob across snapshots
    import glob
    hits = glob.glob(os.path.join(HF, "models--*", "snapshots", "*", name))
    hits = [h for h in hits if os.path.exists(h)]
    return hits[0] if hits else None


def main():
    models = db_models()
    present, missing = [], []
    for m in models:
        (present if resolve(m) else missing).append(m)

    arts = {}
    for bench in sorted(os.listdir(ART)) if os.path.isdir(ART) else []:
        bd = os.path.join(ART, bench)
        if not os.path.isdir(bd):
            continue
        files = os.listdir(bd)
        arts[bench] = {
            "eval_results": sum(1 for f in files if f.endswith("_eval_results.json")),
            "completions_jsonl": sum(1 for f in files
                                     if f.endswith(".jsonl") and not f.endswith(".raw.jsonl")),
            "raw_jsonl": sum(1 for f in files if f.endswith(".raw.jsonl")),
            "total_files": len(files),
        }

    db = sqlite3.connect("file:experiments.sqlite?mode=ro", uri=True)
    n_rows = db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    n_evalres = sum(v["eval_results"] for v in arts.values())

    out = {
        "db_rows": n_rows,
        "models_referenced": len(models),
        "models_present": len(present),
        "models_missing": len(missing),
        "model_coverage_pct": round(100 * len(present) / len(models), 1),
        "artifacts": arts,
        "eval_results_recovered": n_evalres,
        "eval_results_coverage_pct": round(100 * n_evalres / n_rows, 1),
        "present_models": present,
        "missing_models": missing,
    }
    with open("archive_manifest.json", "w") as f:
        json.dump(out, f, indent=1)

    md = ["# Archive manifest\n",
          f"DB rows: **{n_rows}**  |  models referenced: **{len(models)}**  |  "
          f"present: **{len(present)} ({out['model_coverage_pct']}%)**  |  "
          f"missing: **{len(missing)}**\n",
          f"Raw eval results recovered: **{n_evalres} / {n_rows} "
          f"({out['eval_results_coverage_pct']}%)**\n",
          "## Artifacts by bench\n",
          "| bench | eval_results | completions | raw | files |",
          "|---|---|---|---|---|"]
    for b, v in arts.items():
        md.append(f"| {b} | {v['eval_results']} | {v['completions_jsonl']} | "
                  f"{v['raw_jsonl']} | {v['total_files']} |")
    md.append("\n## Present model files\n")
    for m in present:
        md.append(f"- {m}")
    md.append(f"\n## Missing model files ({len(missing)})\n")
    for m in missing:
        md.append(f"- {m}")
    with open("ARCHIVE_MANIFEST.md", "w") as f:
        f.write("\n".join(md) + "\n")

    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("present_models", "missing_models")}, indent=1))


if __name__ == "__main__":
    main()
