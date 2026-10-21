#!/bin/bash
# 一条命令核对并重建整条报告链路：干净 clone 里跑这一个脚本就够。
#
#   ./reproduce.sh
#
# 它按顺序核对：运行时依赖 → 提示集哈希 → 报告输入 → 数据库完整性与清洁度 →
# 陈旧根路径 → 文档检查 → 从库重建 report.html 并与仓库里那份逐字节对比 →
# 报告与产物一致。任何一步失败都以非零退出，缺输入的那一步不会被当成 0。
set -u
# 干净 clone 里没有 /home/z/hf 的 gguf。子项目里凡是「glob 到本机路径就算过」的检查，在这里会**假绿**；
# 所以显式声明本次没有 gguf 源，让那些检查报「未核对」而不是通过（a10 的 build_fixture.py --check 就是这样）。
export A10_NO_GGUF=1
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
         report_inputs/reproducibility.json report_inputs/scheme_effects.json \
         report_inputs/size_claims.json report_inputs/kv_evidence.json \
         report_inputs/bfcl_gap.json report_inputs/moe_feasibility.json \
         report_inputs/bfcl_judge.json report_inputs/gsq.json \
         report_inputs/sampling_collapse.json report_inputs/spec_decode.json \
         docs/subprojects/i02-测量基础设施/non_measurements.tsv docs/docs.schema.yaml; do
    [ -f "$f" ] || { missing_inputs=1; say "missing report input: $f"; }
done
if [ "$missing_inputs" = 0 ]; then
    record PASS "报告输入（mktables / bpw_map / eval_status / open_questions / paired_deltas / reproducibility / 非测量登记册 / docs@1）"
else
    record FAIL "报告输入缺失（见上）"
fi
if python3 checks/readme_counts.py >/dev/null 2>&1; then
    record PASS "README 的入库产物说法与 git ls-files 一致"
else
    record FAIL "README 与 git ls-files 不一致：python3 checks/readme_counts.py"
fi
if python3 report_inputs/build_bfcl_judge.py --check >/dev/null 2>&1; then
    record PASS "bfcl_judge.json 与 a13 的判分器事实一致"
else
    record WARN "bfcl_judge.json 与 a13 的事实不一致：python3 report_inputs/build_bfcl_judge.py"
fi
if python3 report_inputs/build_sampling_collapse.py --check >/dev/null 2>&1; then
    record PASS "sampling_collapse.json 与 a06 的事实一致"
else
    record WARN "sampling_collapse.json 与 a06 的事实不一致：python3 report_inputs/build_sampling_collapse.py"
fi
out=$(python3 report_inputs/build_spec_decode.py --check 2>&1); rc=$?
case "$rc" in
    0) record PASS "spec_decode.json 与 a07 的证据一致" ;;
    2) record SKIP "$(printf '%s' "$out" | grep -m1 '^UNVERIFIED:' | sed 's/^UNVERIFIED: //')" ;;
    *) record WARN "spec_decode.json 与 a07 的证据不一致：python3 report_inputs/build_spec_decode.py" ;;
esac

if python3 checks/spec_decode_negative_control.py >/tmp/reproduce_sd.$$ 2>&1; then
    record PASS "第七/八节的负控（差异改 0 → 正文改口；地板改有差异 → 构建失败）"
else
    record FAIL "$(grep -m1 'FAIL' /tmp/reproduce_sd.$$ | cut -c1-200)"
fi
rm -f /tmp/reproduce_sd.$$

if python3 checks/sampling_collapse_negative_control.py >/dev/null 2>&1; then
    record PASS "第六节厂房档口径的负控（丢题数改 0 → 无差）"
else
    record FAIL "第六节厂商档口径的负控未通过"
fi
if python3 report_inputs/build_gsq.py --check >/dev/null 2>&1; then
    record PASS "gsq.json 与 a10 的事实一致"
else
    record WARN "gsq.json 与 a10 的事实不一致：python3 report_inputs/build_gsq.py"
fi
if python3 checks/gsq_negative_control.py >/dev/null 2>&1; then
    record PASS "第十一节第三方方案口径的负控（1 格改 0 → 全部测不出）"
else
    record FAIL "第十一节第三方方案口径的负控未通过"
fi
if python3 checks/bfcl_judge_negative_control.py >/dev/null 2>&1; then
    record PASS "第十四节判分器口径的负控（改判计数改 0 → 与判分器无关）"
else
    record FAIL "第十四节判分器口径的负控未通过"
fi
if python3 report_inputs/build_moe_feasibility.py --check >/dev/null 2>&1; then
    record PASS "moe_feasibility.json 与 a04 的可行性 fixture 一致"
else
    record WARN "moe_feasibility.json 与 a04 的 fixture 不一致：python3 report_inputs/build_moe_feasibility.py"
fi
if python3 report_inputs/build_bfcl_gap.py --check >/dev/null 2>&1; then
    record PASS "bfcl_gap.json 与现有 BFCL 汇总一致"
else
    record WARN "bfcl_gap.json 与 BFCL 汇总不一致：python3 report_inputs/build_bfcl_gap.py"
fi
# a05 的证据脚本要 `.wrapup/mres` 落盘产物；干净 clone 里没有，所以这里必须把「索引过期」与「看不到输入」分开：
# 前者是 WARN（可重建），后者是 SKIP（索引无法当场核对，随仓库分发的那份即权威，不算通过）。
out=$(python3 report_inputs/build_kv_evidence.py --check 2>&1); rc=$?
case "$rc" in
    0) record PASS "kv_evidence.json 与 a05 的证据脚本输出一致" ;;
    2) record SKIP "$(printf '%s' "$out" | grep -m1 '^UNVERIFIED:' | sed 's/^UNVERIFIED: //')" ;;
    *) record WARN "kv_evidence.json 与 a05 的脚本输出不一致：python3 report_inputs/build_kv_evidence.py" ;;
esac
out=$(python3 report_inputs/build_size_claims.py --check 2>&1); rc=$?
case "$rc" in
    0) record PASS "size_claims.json 与 a02 的通道/曲线产物一致" ;;
    2) record SKIP "$(printf '%s' "$out" | grep -m1 '^UNVERIFIED:' | sed 's/^UNVERIFIED: //')" ;;
    *) record WARN "size_claims.json 与 a02 的产物不一致：python3 report_inputs/build_size_claims.py" ;;
esac
if python3 report_inputs/build_scheme_effects.py --check >/dev/null 2>&1; then
    record PASS "scheme_effects.json 与 a03 归因脚本的输出一致"
else
    record WARN "scheme_effects.json 与 a03 的脚本输出不一致：python3 report_inputs/build_scheme_effects.py"
fi
if python3 report_inputs/build_reproducibility.py --check >/dev/null 2>&1; then
    record PASS "reproducibility.json 与 i01 的地板/幅度事实一致"
else
    record WARN "reproducibility.json 与 i01 的事实不一致：python3 report_inputs/build_reproducibility.py"
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

# 6b) 路由文件（STATUS/FINDINGS/README）里印出的每条引用都要解析得到：
#     迁移把 plan.yaml / result.yaml 搬走后，路由指过去读不到的路径与节点 id 曾长期无人发现。
out=$(python3 checks/router_refs.py 2>&1); rc=$?
case "$rc" in
    0) record PASS "路由文件的引用都可解析（$(printf '%s' "$out" | grep -m1 'resolved' | sed 's/^ *//')）" ;;
    2) record BLOCKED "路由文件缺失：$(printf '%s' "$out" | grep -m1 '^BLOCKED:' | sed 's/^BLOCKED: //')" ;;
    *) record FAIL "路由文件里有无法解析的引用（$(printf '%s' "$out" | grep -c -e 'missing-' -e 'unparsed-')条）：python3 checks/router_refs.py" ;;
esac

# 7) 文档检查（含 schema 标准）与它的负控：一个只会打印 PASS 的检查不算检查
if python3 checks/moe_feasibility_negative_control.py >/tmp/reproduce_mf.$$ 2>&1; then
    record PASS "第四节可行性的负控（超界计数改 0 则从「预算比较」变「分配比较」）"
else
    record FAIL "第四节可行性的负控未通过：python3 checks/moe_feasibility_negative_control.py"
fi
rm -f /tmp/reproduce_mf.$$

if python3 checks/kv_evidence_negative_control.py >/tmp/reproduce_kv.$$ 2>&1; then
    record PASS "第五节 KV 说法的负控（丢/得改 0 则从「逐题在翻」变「无差异」）"
else
    record FAIL "第五节 KV 说法的负控未通过：python3 checks/kv_evidence_negative_control.py"
fi
rm -f /tmp/reproduce_kv.$$

if python3 checks/kv_evidence_unavailable_control.py >/tmp/reproduce_kvu.$$ 2>&1; then
    record PASS "第五节 KV 索引「不可得 ≠ 过期」的负控（缺 .wrapup/mres → exit 2 并点名路径）"
else
    record FAIL "$(grep -m1 'FAIL' /tmp/reproduce_kvu.$$ | cut -c1-160)"
fi
rm -f /tmp/reproduce_kvu.$$

if python3 checks/size_claims_negative_control.py >/tmp/reproduce_sc.$$ 2>&1; then
    record PASS "第二节规模说法的负控（区间改重叠则从「反驳」变「分不出」）"
else
    record FAIL "第二节规模说法的负控未通过：python3 checks/size_claims_negative_control.py"
fi
rm -f /tmp/reproduce_sc.$$

if python3 checks/scheme_effects_negative_control.py >/tmp/reproduce_se.$$ 2>&1; then
    record PASS "方案/厂商结论句的负控（显著则改口、区间加宽则精度跟着变）"
else
    record FAIL "方案/厂商结论句的负控未通过：python3 checks/scheme_effects_negative_control.py"
fi
rm -f /tmp/reproduce_se.$$

if python3 checks/reproducibility_negative_control.py >/tmp/reproduce_rp.$$ 2>&1; then
    record PASS "可复现性边界的负控（幅度改 0 正文改口、删条件后生成失败）"
else
    record FAIL "可复现性边界的负控未通过：python3 checks/reproducibility_negative_control.py"
fi
rm -f /tmp/reproduce_rp.$$

if python3 checks/venv_shebang.py >/tmp/reproduce_vs.$$ 2>&1; then
    record PASS "venv 入口点的 shebang 都指向存在的解释器"
else
    record FAIL "$(grep -m2 'FAIL\|  - ' /tmp/reproduce_vs.$$ | tr '\n' ' ')"
fi
rm -f /tmp/reproduce_vs.$$

if python3 checks/venv_shebang_negative_control.py >/tmp/reproduce_vsn.$$ 2>&1; then
    record PASS "venv shebang 检查的负控（假入口点 → FAIL 并点名；env 入口不误报）"
else
    record FAIL "venv shebang 检查的负控未通过"
fi
rm -f /tmp/reproduce_vsn.$$

if python3 checks/ingest_protocol_negative_control.py >/tmp/reproduce_ip.$$ 2>&1; then
    record PASS "入库协议的负控（只有 fa 不同的两行各成一格、缺协议时明说用了默认值）"
else
    record FAIL "入库协议的负控未通过：python3 checks/ingest_protocol_negative_control.py"
fi
rm -f /tmp/reproduce_ip.$$

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

if python3 checks/refresh_guard_differential_control.py >/tmp/reproduce_rgd.$$ 2>&1; then
    record PASS "「读不到输入就不删」的差分负控（干净 clone 里：带 guard 丢 0 行，去掉 guard 丢数百行）"
else
    record FAIL "$(grep -m1 'FAIL' /tmp/reproduce_rgd.$$ | cut -c1-200)"
fi
rm -f /tmp/reproduce_rgd.$$

if python3 checks/all_exception_null_negative_control.py >/tmp/reproduce_aen.$$ 2>&1; then
    record PASS "全 Exception 写 NULL 的负控（全 Exception→NULL、有通过→实测、没记分数→NULL、旧写法→0.0）"
else
    record FAIL "$(grep -m1 'FAIL' /tmp/reproduce_aen.$$ | cut -c1-200)"
fi
rm -f /tmp/reproduce_aen.$$

if python3 checks/refresh_preserve_negative_control.py >/tmp/reproduce_rp.$$ 2>&1; then
    record PASS "refresh 只动自己的行的负控（三行探针跑两次逐字未变、第二次净改动 0 行）"
else
    record FAIL "$(grep -m1 'FAIL' /tmp/reproduce_rp.$$ | cut -c1-200)"
fi
rm -f /tmp/reproduce_rp.$$

if python3 checks/py_corpus_regrade_check.py >/tmp/reproduce_pcr.$$ 2>&1; then
    record PASS "py 语料取代行与 a14 清单逐条一致、旧行未被改写"
else
    record FAIL "$(grep -m1 '  - ' /tmp/reproduce_pcr.$$ | cut -c1-200)"
fi
rm -f /tmp/reproduce_pcr.$$

out=$(python3 checks/mres_prefix_delete_negative_control.py 2>&1); rc=$?
case "$rc" in
    0) record PASS "REFRESH 删除范围的负控（探针行跑完两次 migrate 仍在、mres/% 行一条不丢、两次行数相同）" ;;
    2) record SKIP "$(printf '%s' "$out" | grep -m1 '不可得:' | sed 's/^不可得: //')" ;;
    *) record FAIL "$(printf '%s' "$out" | grep -m1 'FAIL' | cut -c1-200)" ;;
esac

if python3 checks/superseded_pointer_negative_control.py >/tmp/reproduce_sup.$$ 2>&1; then
    record PASS "superseded 指针的负控（悬空指针 → db_check 变红并点名）"
else
    record FAIL "$(grep -m1 'FAIL' /tmp/reproduce_sup.$$ | cut -c1-160)"
fi
rm -f /tmp/reproduce_sup.$$

if python3 checks/superseded_filter_negative_control.py >/tmp/reproduce_supf.$$ 2>&1; then
    record PASS "报告过滤被取代行的负控（去掉过滤 → 被取代的行以第二个分数回到表里）"
else
    record FAIL "$(grep -m1 'FAIL' /tmp/reproduce_supf.$$ | cut -c1-160)"
fi
rm -f /tmp/reproduce_supf.$$

if python3 checks/docs_dup_id_negative_control.py >/tmp/reproduce_dup.$$ 2>&1; then
    record PASS "doc id 唯一性的负控（同文件重复 → FAIL 并点名；跨文件同名 → PASS）"
else
    record FAIL "doc id 唯一性的负控未通过：python3 checks/docs_dup_id_negative_control.py"
fi
rm -f /tmp/reproduce_dup.$$

if python3 checks/docs_schema_negative_control.py >/tmp/reproduce_negrun.$$ 2>&1; then
    record PASS "docs 检查的负控（缺必填字段 / 枚举外取值都以 1 退出并点名）"
else
    record FAIL "docs 检查的负控未通过：python3 checks/docs_schema_negative_control.py"
fi
rm -f /tmp/reproduce_negrun.$$

# 8) 文档检查：schema 标准缺失是外部阻断，不等同于通过，也不等同于失败
out=$(python3 docs/check_docs.py 2>&1); rc=$?
case "$rc" in
    0) record PASS "docs/check_docs.py（含 doc id 文件内唯一性 + from 可解析，非基线容忍）" ;;
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
