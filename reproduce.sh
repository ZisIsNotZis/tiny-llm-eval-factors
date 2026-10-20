#!/bin/bash
# 一条命令核对并重建整条报告链路：干净 clone 里跑这一个脚本就够。
#
#   ./reproduce.sh
#
# 它按顺序核对：运行时依赖 → 提示集哈希 → 报告输入 → 数据库完整性与清洁度 →
# 陈旧根路径 → 文档检查 → 从库重建 report.html 并与仓库里那份逐字节对比 →
# 报告与产物一致。任何一步失败都以非零退出，缺输入的那一步不会被当成 0。
set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT" || exit 1

declare -a RESULTS=()
FAILED=0

record() {  # record <状态> <说明>
    RESULTS+=("$(printf '%-8s %s' "$1" "$2")")
    [ "$1" = "FAIL" ] && FAILED=1
}

say() { printf '%s\n' "$*"; }

# 1) 运行时依赖：缺什么就说什么，不靠 traceback 才发现
if python3 - <<'PY'
import importlib.util, sys
need = ["numpy", "matplotlib", "yaml", "jsonschema", "referencing"]
missing = [m for m in need if importlib.util.find_spec(m) is None]
if missing:
    print("missing python modules:", ", ".join(missing), file=sys.stderr)
    print("install them with: python3 -m pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)
PY
then
    record PASS "运行时依赖（numpy/matplotlib/yaml/jsonschema/referencing）"
else
    record FAIL "运行时依赖缺失（见上）"
fi

# 2) 提示集哈希：模型看到的题目集必须能当场核对
if [ -f .wrapup/prompts/SHA256SUMS ]; then
    if (cd .wrapup/prompts && sha256sum -c SHA256SUMS >/dev/null 2>&1); then
        record PASS "提示集哈希（$(grep -c . .wrapup/prompts/SHA256SUMS) 份文件）"
    else
        record FAIL "提示集哈希不符：cd .wrapup/prompts && sha256sum -c SHA256SUMS"
    fi
else
    record FAIL "提示集清单缺失：.wrapup/prompts/SHA256SUMS"
fi

# 3) 报告输入是否随仓库分发；这里的输入不在了就什么都别谈
missing_inputs=0
for f in .wrapup/mktables.py .wrapup/bpw_map.json report_inputs/eval_status.json \
         docs/subprojects/i02-测量基础设施/non_measurements.tsv; do
    [ -f "$f" ] || { missing_inputs=1; say "missing report input: $f"; }
done
if [ "$missing_inputs" = 0 ]; then
    record PASS "报告输入（mktables / bpw_map / eval_status / 非测量登记册）"
else
    record FAIL "报告输入缺失（见上）"
fi
if python3 report_inputs/build_eval_status.py --check >/dev/null 2>&1; then
    record PASS "eval_status.json 与现有落盘产物一致"
elif [ ! -d .wrapup/mres ]; then
    record SKIP "eval_status.json 与落盘产物的一致性（本机无 .wrapup/mres 产物，随仓库分发的那份即权威）"
else
    record WARN "eval_status.json 与落盘产物不一致：python3 report_inputs/build_eval_status.py"
fi

# 4) 数据库
if python3 checks/db_check.py >/tmp/reproduce_db_check.$$ 2>&1; then
    record PASS "数据库完整性与清洁度（$(grep -o '[0-9]* rows' /tmp/reproduce_db_check.$$ | head -1)）"
else
    record FAIL "数据库检查未通过：python3 checks/db_check.py"
fi
rm -f /tmp/reproduce_db_check.$$

# 5) 陈旧绝对根路径
if python3 checks/stale_roots.py >/dev/null 2>&1; then
    record PASS "没有可执行脚本硬编码已退役的绝对根路径"
else
    record FAIL "仍有脚本硬编码退役根路径：python3 checks/stale_roots.py"
fi

# 6) 文档检查：schema 标准缺失是外部阻断，不等同于通过，也不等同于失败
out=$(python3 docs/check_docs.py 2>&1); rc=$?
case "$rc" in
    0) record PASS "docs/check_docs.py" ;;
    2) record BLOCKED "docs/check_docs.py：$(printf '%s' "$out" | grep -m1 '^BLOCKED:' | sed 's/^BLOCKED: //' || echo 'docs@1 标准缺失')" ;;
    *) record FAIL "docs/check_docs.py 退出 $rc：$(printf '%s' "$out" | grep -m3 '  - ' | tr '\n' ' ')" ;;
esac

# 7) 从库重建报告，并与仓库里那份逐字节对比
if [ -f report.html ]; then
    before=$(sha256sum report.html | cut -d' ' -f1)
else
    before=""
fi
if python3 make_report.py >/tmp/reproduce_report.$$ 2>&1; then
    after=$(sha256sum report.html | cut -d' ' -f1)
    if [ -n "$before" ] && [ "$before" = "$after" ]; then
        record PASS "report.html 从库重建后逐字节相同（$(wc -c <report.html) 字节，${after:0:12})）"
    else
        record FAIL "report.html 重建后与仓库里那份不同（仓库 ${before:0:12} 重建 ${after:0:12}）"
    fi
else
    record FAIL "报告构建失败（见 /tmp/reproduce_report.$$）"
fi

# 8) 报告与产物一致
if python3 checks/report_check.py >/tmp/reproduce_repchk.$$ 2>&1; then
    record PASS "报告与产物一致（行标签唯一、题量取自产物、非测量登记册在场）"
else
    record FAIL "报告与产物不一致：python3 checks/report_check.py"
fi

say ""
say "== 复现核对 =="
for line in "${RESULTS[@]}"; do say "  $line"; done
say ""
if [ "$FAILED" = 1 ]; then
    say "FAILED：上面标记 FAIL 的步骤未通过。"
    exit 1
fi
say "OK：报告可从库重建，且与仓库里的 report.html 逐字节相同。"
say "    （BLOCKED/SKIP 行是未验证或外部阻断，不算通过。）"
