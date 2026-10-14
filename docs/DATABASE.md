# 数据库：schema、备份、清洁规则

## 唯一数据源

`experiments.sqlite` 是结果的**唯一真实来源**，一次运行一行。派生列以 `__` 开头（`__size`/`__quant`/`__quant_ratio`…）。
分析脚本只读（`mode=ro`）。

## 备份规则

**任何改动前先做编号备份**：`cp experiments.sqlite experiments.sqlite.bakN`（N 递增）。
改完跑完整性/清洁检查。

## 清洁检查（每次入库后）

- `PRAGMA integrity_check` = ok
- `PRAGMA foreign_key_check` = 空
- 必填字段无 null/空（`model`、`_bench`）
- `_score` ∈ [0,1]（例外：`bench_family='speed'` 的 15 行 `_score IS NULL`，速度存 `_tok_s`）
- **`总行数 == 按全部列 distinct 的行数`**

## 去重事件（2026-10-14）与教训

`experiments.sqlite` 累积了**逐列完全相同的重复行**。根因：`migrate_db.py` 对逐语言 MultiPL-E 路径**非幂等**；
一个自动 finisher 每 10 分钟跑一次它，跑了 ~13 h，把冗余从 ~1800 行放大到 9564 行（12871 行里只有 3307 唯一）。

处理：备份 `experiments.sqlite.bak34` → 用 `SELECT DISTINCT <全部 47 列>` 重建表 → 重建 5 个索引 → 校验通过
（行数 12871→3307、`integrity ok`、`fk` 空、必填空、所有 tag 仍在）。因为重复是逐列相同的（含 `rep`），
信息量为零，分析脚本按 distinct 值聚合/用存储的 `n_items`，结论未受影响（F9/F12/F13 复算不变）。

**规则**：不要按时间表跑 `migrate_db.py`；每次入库只跑一次并校验 `总行数 == distinct`。
若确需重复跑，先把逐语言入库改成 `DELETE FROM experiments WHERE run_tag=?` 再插（`ingest_m22` 已是此模式）。

## schema 缺口（不可审计的历史）

`ctx_size`、`parallel_slots`、`seed`、`protocol`、`run_tag`、`language`、`bench_family`、`source_file`、`completed_at`、
`_tok_s`、`n_items` 等是后来才加的；早期约 1881 行 legacy 记录这些列为空，因此任何 `ctx=`/`parallel=` 作用域**不可审计**。
