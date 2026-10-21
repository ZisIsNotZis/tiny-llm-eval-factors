# checks — i02 的基础设施检查

这个目录归 i02（测量基础设施）。每个脚本证明一件事，都以退出码说话，`./reproduce.sh` 依次调用它们。

| 命令 | 证明什么 | 失败时说明 |
|---|---|---|
| `python3 checks/db_check.py` | 库结构完好、外键无冲突、必填字段非空、取值域不越界、没有重复的测量身份 | 只读；逐条列出违规行数 |
| `python3 checks/report_check.py` | 生成的 `report.html` 与产物一致：行标签唯一、印出的题量等于该格产物的题量、非测量登记册在场、无法区分两个值的格把两个值都印出来 | 读 `report.html` 与 `report_inputs/`，不读构建中间量 |
| `python3 checks/stale_roots.py` | 没有可执行脚本再引用已退役的绝对根路径 | `--fix` 是幂等迁移；改完自动 `bash -n` / `py_compile` |
| `python3 checks/docs_schema_negative_control.py` | `docs/check_docs.py` 真的会失败：未改动副本 PASS，缺必填字段 / 枚举外取值都以 1 退出并点名 | 在临时目录里做，不动仓库 |
| `python3 checks/router_refs.py` | 三个路由文件（`STATUS.md`/`FINDINGS.md`/`README.md`）里印出的每条 `docs/…::id` 引用与每个 `docs/…` 路径都在树里解析得到；扫空不算通过 | 只判可解析，不判正文真假；逐条 `file:line token reason`，末行给解析比 |

不属于这里的检查：`docs/check_docs.py` 属于文档层（在 `docs/` 下），`report_inputs/build_eval_status.py --check`
属于输入本身（在 `report_inputs/` 下）。
