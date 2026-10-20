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

# 2) CJK 字体：它是被复现条件的一部分——换字体，每张图的字形与度量都变。
#    路径与期望哈希只有一个家（make_report.py 的常量），这里问它，不另抄一份。
if font=$(python3 -c "import make_report as m; print(m.CJK_FONT, m.CJK_FONT_SHA256)" 2>/tmp/reproduce_font.$$); then
    record PASS "CJK 字体 $font（存在且 sha256 匹配）"
else
    record FAIL "$(tr '\n' ' ' < /tmp/reproduce_font.$$)"
fi
rm -f /tmp/reproduce_font.$$

# 3) 提示集哈希：模型看到的题目集必须能当场核对
if [ -f .wrapup/prompts/SHA256SUMS ]; then
    if (cd .wrapup/prompts && sha256sum -c SHA256SUMS >/dev/null 2>&1); then
        record PASS "提示集哈希（$(grep -c . .wrapup/prompts/SHA256SUMS) 份文件）"
    else
        record FAIL "提示集哈希不符：cd .wrapup/prompts && sha256sum -c SHA256SUMS"
    fi
else
    record FAIL "提示集清单缺失：.wrapup/prompts/SHA256SUMS"
fi

# 4) 报告输入是否随仓库分发；这里的输入不在了就什么都别谈
missing_inputs=0
for f in .wrapup/mktables.py .wrapup/bpw_map.json report_inputs/eval_status.json \
         report_inputs/open_questions.json report_inputs/paired_deltas.json \
         docs/subprojects/i02-测量基础设施/non_measurements.tsv docs/docs.schema.yaml; do
    [ -f "$f" ] || { missing_inputs=1; say "missing report input: $f"; }
done
if [ "$missing_inputs" = 0 ]; then
    record PASS "报告输入（mktables / bpw_map / eval_status / open_questions / 非测量登记册 / docs@1）"
else
    record FAIL "报告输入缺失（见上）"
fi
if python3 report_inputs/build_paired_deltas.py --check >/dev/null 2>&1; then
    record PASS "paired_deltas.json 与 a01 的配对差事实一致"
else
    record WARN "paired_deltas.json 与 a01 的事实不一致：python3 report_inputs/build_paired_deltas.py"
fi
if python3 report_inputs/build_open_questions.py --check >/dev/null 2>&1; then
    record PASS "open_questions.json 与各子项目 PLAN.md 的「未解问题」一节一致"
else
    record WARN "open_questions.json 与 PLAN.md 不一致：python3 report_inputs/build_open_questions.py"
fi
if python3 report_inputs/build_eval_status.py --check >/dev/null 2>&1; then
    record PASS "eval_status.json 与现有落盘产物一致"
elif [ ! -d .wrapup/mres ]; then
    record SKIP "eval_status.json 与落盘产物的一致性（本机无 .wrapup/mres 产物，随仓库分发的那份即权威）"
else
    record WARN "eval_status.json 与落盘产物不一致：python3 report_inputs/build_eval_status.py"
fi

# 5) 数据库
if python3 checks/db_check.py >/tmp/reproduce_db_check.$$ 2>&1; then
    record PASS "数据库完整性与清洁度（$(grep -o '[0-9]* rows' /tmp/reproduce_db_check.$$ | head -1)）"
else
    record FAIL "数据库检查未通过：python3 checks/db_check.py"
fi
rm -f /tmp/reproduce_db_check.$$

# 6) 陈旧绝对根路径
if python3 checks/stale_roots.py >/dev/null 2>&1; then
    record PASS "没有可执行脚本硬编码已退役的绝对根路径"
else
    record FAIL "仍有脚本硬编码退役根路径：python3 checks/stale_roots.py"
fi

# 7) 文档检查（含 schema 标准）与它的负控：一个只会打印 PASS 的检查不算检查
if python3 checks/ingest_skip_negative_control.py >/tmp/reproduce_is.$$ 2>&1; then
    record PASS "入库跳过报告的负控（未知名逐条报出、认得的名字跳过计数为 0）"
else
    record FAIL "入库跳过报告的负控未通过：python3 checks/ingest_skip_negative_control.py"
fi
rm -f /tmp/reproduce_is.$$

if python3 checks/paired_delta_negative_control.py >/tmp/reproduce_pd.$$ 2>&1; then
    record PASS "配对差叙述的负控（区间全跨 0 时报告改口，不声称掉点）"
else
    record FAIL "配对差叙述的负控未通过：python3 checks/paired_delta_negative_control.py"
fi
rm -f /tmp/reproduce_pd.$$

if python3 checks/open_questions_negative_control.py >/tmp/reproduce_oq.$$ 2>&1; then
    record PASS "未解问题索引的负控（工作包标题与围栏里的标题都不算一节）"
else
    record FAIL "未解问题索引的负控未通过：python3 checks/open_questions_negative_control.py"
fi
rm -f /tmp/reproduce_oq.$$

if python3 checks/docs_schema_negative_control.py >/tmp/reproduce_negrun.$$ 2>&1; then
    record PASS "docs 检查的负控（缺必填字段 / 枚举外取值都以 1 退出并点名）"
else
    record FAIL "docs 检查的负控未通过：python3 checks/docs_schema_negative_control.py"
fi
rm -f /tmp/reproduce_negrun.$$

# 8) 文档检查：schema 标准缺失是外部阻断，不等同于通过，也不等同于失败
out=$(python3 docs/check_docs.py 2>&1); rc=$?
case "$rc" in
    0) record PASS "docs/check_docs.py" ;;
    2) record BLOCKED "docs/check_docs.py：$(printf '%s' "$out" | grep -m1 '^BLOCKED:' | sed 's/^BLOCKED: //' || echo 'docs@1 标准缺失')" ;;
    *) record FAIL "docs/check_docs.py 退出 $rc：$(printf '%s' "$out" | grep -m3 '  - ' | tr '\n' ' ')" ;;
esac

# 9) 从库重建报告，并与仓库里那份逐字节对比
if [ -f report.html ]; then
    before=$(sha256sum report.html | cut -d' ' -f1)
else
    before=""
fi
BUILD_OK=0
if python3 make_report.py >/tmp/reproduce_report.$$ 2>&1; then
    BUILD_OK=1                       # 本次真的产出了报告：后面的报告检查据此放行
    after=$(sha256sum report.html | cut -d' ' -f1)
    if [ -n "$before" ] && [ "$before" = "$after" ]; then
        record PASS "report.html 从库重建后逐字节相同（$(wc -c <report.html) 字节，${after:0:12})）"
    else
        record FAIL "report.html 重建后与仓库里那份不同（仓库 ${before:0:12} 重建 ${after:0:12}）"
    fi
else
    record FAIL "报告构建失败（见 /tmp/reproduce_report.$$）"
fi

# 10) 报告与产物一致——只在本次真的产出了报告时做；否则拿仓库里那份旧文件冒充
if [ "$BUILD_OK" = 1 ]; then
    if python3 checks/report_check.py >/tmp/reproduce_repchk.$$ 2>&1; then
        record PASS "报告与产物一致（行标签唯一、题量取自产物、非测量登记册在场）"
    else
        record FAIL "报告与产物不一致：python3 checks/report_check.py"
    fi
else
    record SKIP "报告与产物一致（第 9 步没有产出本次报告，不拿仓库里那份旧文件比对）"
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
