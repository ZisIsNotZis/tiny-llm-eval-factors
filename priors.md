# Priors

* [high] EvalPerf is directly supported in EvalPlus and introduces an efficiency axis (DPS on performance-exercising tasks) that is distinct from correctness-only pass rates. | source: https://raw.githubusercontent.com/evalplus/evalplus/master/docs/evalperf.md | scope: benchmark capability and metric definition, not model-specific outcome.
* [high] KV quant byte-ratio mapping used in this project is grounded in `llama.cpp` quant block definitions: `fp16=1.0`, `q8_0=0.53125`, `q5_1=0.375`, `q5_0=0.34375` (ratio vs fp16). | source: local `~/llama.cpp` (`ggml-common.h` block layout constants) | scope: KV ratio encoding in score/time formula features.
* [high] `evalplus` OpenAI codegen path with sampling flags requires a positive temperature; `temperature=0.0` with non-greedy sampling options is invalid in this harness path. | source: local `~/evalplus/evalplus/codegen.py` behavior observed in run failures | scope: experiment launcher parameter validity.
