# 工具 / 环境 / harness 的经验（可复用规则）

> 层级：**L1 客观规范/事实**（工具/环境/harness 的可复用规则）。

这里是可复用的纪律与已定位的坑，不是运行流水。

## GPU 独占与锁

- 同一时刻只有一个 GPU 任务，用 `flock /tmp/llama_gpu.lock`（`.wrapup/gpu_locked.sh`）串行。
- **存活判定只用 `flock -n` 或日志完成横幅**，绝不用 `pgrep -f "<脚本名>"`（会匹配任何命令行提到该名字的进程，
  以及别的项目的进程；曾造成 1.6 h 假忙与多次误判）。
- **孤儿 server 会继承锁**：面板父进程退出但 `llama-server` 子进程仍持有 `/tmp/llama_gpu.lock`，会让下一个面板一直等。
  用 `fuser -v /tmp/llama_gpu.lock` 找持有者，只杀孤儿的锁持有子进程，绝不等待。
- 面板脚本必须有 `trap cleanup EXIT`，退出时关掉自己的 server；启动前检查端口，若是**别人的** server 占用则中止，
  若匹配我们自己的陈旧 server 则先杀——否则会健康检查到上一个 server、把**错误模型**当成新 tag 打分。
- 外来项目常驻（如 :8834 的 `Spark-X2.5-4B`）不属于我们，不持有我们的锁，**不动它**；但它占用显存，会导致大模型 OOM。

## 加载门控（load gate）

- 跑任何面板前，先用 CPU 载入一次（`llama-cli -ngl 0` 或 `.wrapup/loadgate_cpu.sh`）确认能加载，写 `.wrapup/loadgate.jsonl`。
- 加载失败（新 ggml 类型、diffusion 架构等）记 `FAIL` 并排除，**不产出 null**。
- 已知：build 4399 支持 type 42(`Q2_0`) 定义但混合 SSM 架构可能仍失败；type 142(`PQ2_0`)、
  143(`PTQ1_0`) 超出 `GGML_TYPE_COUNT=43`，需要另建更新的 llama.cpp；`diffusion-gemma` 架构本机任何构建都不认。

## 入库（ingest）与数据库

- `migrate_db.py` 是唯一入库路径；每个面板在 `main()` 注册一行（`ONCE` 或 `REFRESH`）。
- `REFRESH` = 先按 `run_tag` 删除再插入（用于追加数小时的面板）；summary 文件是 refresh 的唯一来源，
  **清空 summary 等于删掉该细胞**。
- **`migrate_db.py` 对逐语言 MultiPL-E 路径非幂等**：定时反复跑会累积完全相同行。**不要按时间表跑**；
  每次入库只跑一次，跑完校验 `总行数 == distinct 行数`。详见 `DATABASE.md`。

## 0.00 的处理

- `0.00` 先怀疑 harness，再怀疑能力：检查每槽上下文、是否用了原生 FC handler、是否在重算陈旧结果文件。
- 常见 silent-zero 来源：handler 方言不匹配（模型用散文回答，判 0）；`-c N -np K` 每槽上下文不足；
  BFCL 默认从陈旧结果文件恢复（结果路径按 handler 而非 run_tag）。
- 真实的地板是可能的（例：granite Q2_K 在正确 handler 下仍 0.00，是真实悬崖）。

## 环境

- HF 官方域名在本机解析到被投毒地址、`hf-mirror` 会挂起 → 用项目既有的 ModelScope 通道下载。
- 对数似然任务需要本仓库的精确回显 shim（`.wrapup/lmeval_run.py`），stock `lm_eval --model gguf` 会 KeyError。
- 离线环境变量 `HF_HUB_OFFLINE=1` 等必须设，否则一次 DNS 抖动让任务返回 null。
