# Resources

* 4090 24G
* 100Mbps internet
* 1.8TB ssd at ~/hf, holding models and datasets
* ~/.local/bin/llama-server (or other programs you need)
* ~/evalplus/
* `experiments.sqlite` is the source-of-truth DB; numbered backups exist up to `.bak42`
* Current key artifacts:
  - `.serial_formula_search_caps.csv` (serial cap-family exact-formula search results, timed)
  - `.manualeig6_nemotron.log`, `.manualeig7_granite_kv.log`, `.manualeig8_granite_longctx_kv.log`, `.manualeig9_granite_longctx_kv_mbpp.log`
  - `.manualeig10_qwen4b_quantmix.log`, `.manualeig12_gemmae2b_quantmix.log`, `.manualeig13_qwen2b_quantmix.log`
* Environment limitations:
  - strict 35B q8/q8 same-scale continuation OOMs on this 24GB host
  - EvalPerf requires privileged `perf_event_paranoid` change (blocked here)
