# Local Language-Model Research

This repository is a reproducible research workbench for measuring local language-model inference factors, including quantization, model size, decoding protocols, and benchmark behavior. It is research evidence, not a model release or a claim that every planned comparison is complete.

## Source of truth

- `experiments.sqlite` is the data source of truth for recorded measurements.
- `docs/plan/plan.yaml` owns current research questions and their states.
- `docs/result/result.yaml` owns the current findings and their evidence references.
- `AGENTS.md` defines data-trust, experiment, and database-safety rules.
- `make_report.py` produces the derived `report.html`; do not edit the generated report by hand.
- `.wrapup/` contains local run outputs, downloaded corpora, and other regenerable or resumable experiment artifacts; its ignore rules keep those out of Git unless a specific durable evidence artifact is intentionally promoted.

Unknown, blocked, or unmeasured results must remain distinct from zero or a negative result. Consult the owning plan/result entries before interpreting any number, and preserve the recorded workload and protocol alongside comparisons.

## License

Original code and documentation retain the repository's existing MIT license; see `LICENSE`. Model weights, benchmark datasets, and other third-party materials keep their own licenses and are not relicensed by this notice.
