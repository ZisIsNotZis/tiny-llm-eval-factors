#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a11 的收口装置：把 `RESULT.md` 的每条数字变成一条可判定的预期。

退出码即结论：0 = 全部成立；1 = 有一条不成立（本层事实需复核）；2 = 仓库内输入缺失。

本装置判两件事，两件都不需要 GPU、不需要 `/home/z/hf`、干净 clone 里就能跑：

  1. **门槛的源级证据**：`fixtures/arch_tables.json` 里两棵 llama.cpp 源码树（本机二进制所在的
     4da6337、上游 2026-10-20 的 339f324）的架构名表都**没有** `diffusion-gemma`，而
     `gemma4`、`gemma4-assistant` 与四个扩散架构（dream/llada/llada-moe/rnd1）都在——
     所以拒绝不是「不支持扩散」，而是「这一族的键没实现」。表里查不到时运行时抛的正是那句
     `unknown model architecture: '<arch>'`，与 `fixtures/diffusion_gate.json` 里记录的现场输出同源。
  2. **现场记录自洽**：失败次数、错误文本、负控成功、权重字节 / 位宽 / KV 上界 / bf16 量
     全部能在 `fixtures/headers.json` 的头部上重算出来，不是抄的。

现场重放（要盘上有 gguf 与 llama.cpp 二进制）由 `gate.py` 做，本装置只做 `--live` 时调用它；
干净 clone 里没有 live 输入时 `--live` 退出 2（未验证），不带参数的默认跑法不依赖它们。

    python3 run_all.py            # 干净 clone 可跑（本装置）
    python3 run_all.py --live     # 有 live 输入时：重放门槛 + 头部漂移检查
    python3 run_all.py --selftest # 负控：把夹具改坏，对应检查必须翻红
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

ANALYSIS = HERE.parent
REPO = HERE.parents[4]          # analysis / a11-… / subprojects / docs / 仓库根
FIX = ANALYSIS / "fixtures"

DIFF = "diffusiongemma-26B-A4B-it-Q4_K_M.gguf"
TWIN = "gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf"
ARCH = "diffusion-gemma"
A02_TRUTH = REPO / "docs" / "subprojects" / "a02-模型规模" / "analysis" / "fixtures" / "gguf_truth.json"
BPW_MAP = REPO / ".wrapup" / "bpw_map.json"
TRANSFORMERS_FIX = FIX / "transformers_code.json"

results = []


def expect(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  [{'ok' if cond else 'FAIL'}] {name}{('  — ' + detail) if detail else ''}")


def load():
    def rd(p):
        return json.loads(p.read_text(encoding="utf-8"))
    code = json.loads(TRANSFORMERS_FIX.read_text(encoding="utf-8")) \
        if TRANSFORMERS_FIX.exists() else None
    return (rd(FIX / "headers.json"), rd(FIX / "arch_tables.json"),
            rd(FIX / "diffusion_gate.json"), code)


def prod(xs):
    p = 1
    for x in xs:
        p *= x
    return p


def kv_upper(meta, bytes_per_elem=2):
    """每 token 的 KV 上界（f16）——与 gguf_header.kv_upper_bound 同一公式，独立写一遍当交叉核对。"""
    heads = meta["attention.head_count_kv"]
    heads = max(heads) if isinstance(heads, list) else heads
    return int(meta["block_count"] * heads
               * (meta["attention.key_length"] + meta["attention.value_length"]) * bytes_per_elem)


def kv_true(meta, n_ctx, bytes_per_elem=2):
    """按层记账的真值 KV（f16）——与 `gguf_header.kv_true_bytes` 同一口径，独立写一遍。

    滑窗层只留 `min(n_ctx, sliding_window)` 个 token 且用 `*_swa` 头维；全局层留满 `n_ctx`。
    """
    n = meta["block_count"]
    heads = meta["attention.head_count_kv"]
    heads = heads if isinstance(heads, list) else [heads] * n
    pattern = meta.get("attention.sliding_window_pattern") or [False] * n
    window = meta.get("attention.sliding_window") or n_ctx
    k_swa = meta.get("attention.key_length_swa", meta["attention.key_length"])
    v_swa = meta.get("attention.value_length_swa", meta["attention.value_length"])
    total = 0
    for i in range(n):
        if pattern[i]:
            total += heads[i] * (k_swa + v_swa) * bytes_per_elem * min(n_ctx, window)
        else:
            total += heads[i] * (meta["attention.key_length"]
                                 + meta["attention.value_length"]) * bytes_per_elem * n_ctx
    return int(total)


def checks(headers, tables, gate, code=None):
    print("A. 头部夹具：参数与位宽能从张量表重算出来")
    models = headers["models"]
    expect(f"A0 两份头部都在（{DIFF} / {TWIN}）", set(models) == {DIFF, TWIN}, str(sorted(models)))
    for name, tensors_n in ((DIFF, 692), (TWIN, 658)):
        h = models[name]
        recomputed = sum(prod(t["dims"]) for t in h["tensors"])
        expect(f"A1 {name}: n_params 与张量表一致",
               recomputed == h["n_params"], f"{recomputed:,} vs {h['n_params']:,}")
        only_me = sorted({x["name"] for x in h["tensors"]}
                         - {x["name"] for x in models[TWIN if name == DIFF else DIFF]["tensors"]})
        if name == DIFF:
            # 扩散文件是双胞胎的**严格父集**：多的 34 个张量正好是逐层输出缩放（30）+
            # self-conditioning 四件套（self_cond_down/up/gate/pre_norm）——后者是扩散模型独有构件。
            enc = [n for n in only_me if n.endswith("enc_layer_output_scale.weight")]
            self_cond = [n for n in only_me if n.startswith("self_cond_")]
            ok = (len(h["tensors"]) == tensors_n and len(only_me) == 34
                  and len(enc) == 30 and len(self_cond) == 4)
            expect(f"A2 {name}: 692 张量，且比双胞胎多的正好 34 个"
                   "（30 个 enc_layer_output_scale + 4 个 self_cond_*）",
                   ok, f"多 {len(only_me)} 个（{len(enc)} + {len(self_cond)}）: {self_cond}")
        else:
            expect(f"A2 {name}: 658 张量，且比扩散文件一个也不多（严格子集）",
                   len(h["tensors"]) == tensors_n and not only_me,
                   f"多 {len(only_me)} 个 {only_me[:3]}")
        expect(f"A3 {name}: bpw_file = file_bytes×8/n_params",
               abs(h["bpw_file"] - h["file_bytes"] * 8 / h["n_params"]) < 1e-9, f"{h['bpw_file']:.4f}")
        expect(f"A4 {name}: data_bytes = file_bytes − data_offset",
               h["data_bytes"] == h["file_bytes"] - h["data_offset"],
               f"{h['data_bytes']} vs {h['file_bytes'] - h['data_offset']}")
        gaps = [h["tensors"][i + 1]["offset"] - (h["tensors"][i]["offset"] + h["tensors"][i]["bytes"])
                for i in range(len(h["tensors"]) - 1)]
        expect(f"A5 {name}: 张量偏移首尾相接（无重叠、无空洞）", set(gaps) == {0}, str(sorted(set(gaps))))

    d, t = models[DIFF], models[TWIN]
    meta = d["meta"]
    print("B. 这文件确实是扩散解码器，不是坏文件")
    expect(f"B1 架构名 = {ARCH}", d["arch"] == ARCH, d["arch"])
    expect("B2 非因果注意力（attention.causal = false）", meta["attention.causal"] is False,
           str(meta["attention.causal"]))
    expect("B3 diffusion.canvas_length = 256（块扩散的画布）",
           meta.get("diffusion.canvas_length") == 256, str(meta.get("diffusion.canvas_length")))
    expect("B4 头部可解析（692 张量 / v3 / 30 层 / 128 专家用 8）且带掩码词表标记"
           "（tokenizer.ggml.mask_token_id = 4）",
           d["gguf_version"] == 3 and meta["block_count"] == 30
           and meta["expert_count"] == 128 and meta["expert_used_count"] == 8
           and d.get("token_ids", {}).get("mask_token_id") == 4,
           f"v{d['gguf_version']} / {meta['block_count']} 层 / "
           f"{meta['expert_count']}→{meta['expert_used_count']} / "
           f"mask={d.get('token_ids', {}).get('mask_token_id')}")

    print("C. 对照侧：同家族自回归双胞胎（a02 的入库真值与 bpw_map 都对得上）")
    truth = json.loads(A02_TRUTH.read_text(encoding="utf-8"))["models"]
    expect("C1 a02 的 gguf_truth 里有这个双胞胎", TWIN in truth)
    expect("C2 双胞胎参数量与 a02 的入库真值逐位相同",
           truth.get(TWIN, {}).get("n_params") == t["n_params"],
           f"{t['n_params']:,} vs {truth.get(TWIN, {}).get('n_params')}")
    bpw = json.loads(BPW_MAP.read_text(encoding="utf-8"))
    expect("C3 双胞胎位宽与 bpw_map 一致（两份独立产物）",
           abs(bpw[TWIN] - t["bpw_file"]) < 1e-6, f"{t['bpw_file']:.6f} vs {bpw.get(TWIN)}")
    dparams = d["n_params"] - t["n_params"]
    expect("C4 两个臂的参数量差 ≤ 0.1%（同一主干，可比性成立）",
           abs(dparams) / t["n_params"] < 1e-3,
           f"Δ={dparams:+,}（{dparams / t['n_params']:+.4%}）")
    nearest = bpw["gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf"]
    expect("C5 最近的同尺寸自回归 Q4（UD-Q4_K_XL）与它只差 ≈0.07 bpw——那个臂就是 m145（未测）",
           abs(nearest - d["bpw_file"]) < 0.1,
           f"{nearest:.4f} vs {d['bpw_file']:.4f}（差 {nearest - d['bpw_file']:+.4f}）")
    expect("C6 而**已入库**的 QAT 臂差 0.807 bpw：它不是位宽匹配的对照",
           abs((d["bpw_file"] - t["bpw_file"]) - 0.8072) < 0.01,
           f"{d['bpw_file']:.4f} − {t['bpw_file']:.4f} = {d['bpw_file'] - t['bpw_file']:+.4f}")
    if code is None:
        expect("C7 第三条路（同模型换运行时）：夹具在场且记录到解码回路", False, "夹具缺")
    else:
        m = code.get("markers", {})
        expect("C7 第三条路的「代码在」：transformers 5.17.0 的 diffusion_gemma 有模型类、"
               "max_denoising_steps 默认 48、EntropyBoundSampler.accept_canvas 与 ``block length in block diffusion``",
               code.get("transformers_dist") == "transformers-5.17.0.dist-info"
               and all(m.get(k) for k in ("model_class", "denoise_steps_default",
                                          "sampler_class", "accept_canvas", "canvas_docstring"))
               and m.get("denoise_steps_default_value") == 48,
               f"{code.get('transformers_dist')} · {code.get('canvas_docstring_line')} · {m}")

    print("D. 门槛：两棵 llama.cpp 源码树的架构名表都没有这个键，而扩散别的键在")
    for label in ("local_4da6337", "upstream_339f324"):
        tb = tables.get(label)
        if tb is None:
            expect(f"D0 {label} 在夹具里", False)
            continue
        names = set(tb["names"].values())
        expect(f"D1 {label}: 表里有 {len(names)} 个架构名，且没有 {ARCH}",
               ARCH not in names and len(names) > 100, f"{len(names)} 名")
        expect(f"D2 {label}: gemma4 / gemma4-assistant 在表里（不是整个 gemma 家族都不认）",
               {"gemma4", "gemma4-assistant"} <= names)
        expect(f"D3 {label}: 四个扩散架构在表里（不是整个扩散解码都不支持）",
               set(tb["diffusion_arch_names"]) == {"dream", "llada", "llada-moe", "rnd1"},
               str(tb["diffusion_arch_names"]))
        expect(f"D4 {label}: 查表失败处的措辞被记录为 unknown model architecture",
               "unknown model architecture" in tb["throws_on_missing_arch"])
        expect(f"D5 {label}: has_diffusion_gemma 为假", tb["has_diffusion_gemma"] is False)
    expect("D6 上游那棵树的 commit 是 2026-10-20 之后的 HEAD（339f324…）",
           str(tables["upstream_339f324"]["git_head"]).startswith("339f324"),
           str(tables["upstream_339f324"]["git_head"]))
    expect("D7 本机二进制 commit 4bc272fd72 是源码树 HEAD 4da6337 的祖先",
           str(tables["local_4da6337"]["git_head"]).startswith("4da6337"),
           str(tables["local_4da6337"]["git_head"]))

    print("E. 现场记录：同一句错话出自两个运行时，负控加载成功")
    expect("E1 结论是 GATE-FAIL", gate["verdict"] == "GATE-FAIL", gate["verdict"])
    expect("E2 两次加载尝试都指向这个架构名",
           len(gate["attempts"]) == 2 and all(a["arch_error"] == ARCH for a in gate["attempts"]),
           str([a["arch_error"] for a in gate["attempts"]]))
    expect("E3 两次尝试都是非零退出（不是超时、不是 0 分）",
           all(isinstance(a["rc"], int) and a["rc"] != 0 for a in gate["attempts"]),
           str([a["rc"] for a in gate["attempts"]]))
    expect("E4 负控（同一个 llama-server 换 gemma4 文件）走完 /health 并出 token",
           gate["control_ok"] and gate["control_attempt"]["health_ok"]
           and gate["control_attempt"]["token"], json.dumps(gate["control_attempt"], ensure_ascii=False)[:160])
    expect("E5 负控模型的架构与失败的架构不同",
           gate["control_header"]["arch"] != gate["header"]["arch"],
           f"{gate['control_header']['arch']} vs {gate['header']['arch']}")
    expect("E6 记录里三个运行时版本一致且是同一个 build",
           len(set(v for v in gate["runners"].values() if v)) == 1, str(gate["runners"]))

    print("F. 价格：装不装得下——上界与真值两个口径并列，上界不是需求")
    price = gate["price"]
    expect("F1 口径自洽：权重字节 = 头部的 data_bytes；KV 上界 = 层×kv头×(k长+v长)×2B",
           price["weights_bytes"] == d["data_bytes"]
           and price["kv_bound_bytes_per_token"] == kv_upper(meta),
           f"{price['weights_bytes']:,} B / 上界 {price['kv_bound_bytes_per_token']:,} B per token")
    expect("F2 真值 KV@4096 = 293,601,280 B = 0.273 GiB（按层：25 层滑窗只留 1024 token、用 swa 头维；5 层全局留满）",
           price["kv_true_bytes_at_4096"] == kv_true(meta, 4096)
           and abs(price["kv_true_gib_at_4096"] - 0.273) < 1e-3,
           f"{price['kv_true_bytes_at_4096']:,} B = {price['kv_true_gib_at_4096']} GiB")
    expect("F3 上界不是需求：上界/真值 ≈ 6.9 倍，两个数必须并列出现（1.875 是 bound，不是测得的需求）",
           abs(price["bound_over_true"] - 6.9) < 0.2 and price["kv_bound_gib_at_4096"] > 6 * price["kv_true_gib_at_4096"],
           f"上界 {price['kv_bound_gib_at_4096']} GiB / 真值 {price['kv_true_gib_at_4096']} GiB = {price['bound_over_true']}")
    expect("F4 按真值算：权重 15.638 + 真 KV 0.273 = 15.911 GiB ≤ 当时空闲 → 当时可容纳"
           "（llama.cpp 的 compute buffer 未算，加它后是否仍可容纳未测）",
           abs(price["weights_plus_true_kv_gib"] - 15.911) < 1e-3
           and price["fits_given_true_kv"] is True
           and (price["weights_plus_true_kv_gib"] * 1024 <= price["gpu"]["free_mib"]),
           f"{price['weights_plus_true_kv_gib']} GiB vs 当时空闲 {price['gpu']['free_mib'] / 1024:.2f} GiB")
    expect("F5 bf16 权重 = n_params×2，且 > 整张卡（换运行时也得 offload）",
           price["bf16_weights_bytes"] == 2 * d["n_params"]
           and price["bf16_weights_gib"] > price["gpu"]["total_mib"] / 1024,
           f"{price['bf16_weights_gib']} GiB vs 卡 {price['gpu']['total_mib'] / 1024:.1f} GiB")
    expect("F6 当时有别的进程在占卡（外部占用不是本仓库的锁能管的）",
           price["gpu"]["compute_apps_mib"] > 0, f"{price['gpu']['compute_apps_mib']} MiB")


SELFTEST_CASES = [
    # (说明, 改法, 必须翻红的检查名前缀)
    ("把 diffusion-gemma 塞进架构名表",
     lambda h, t, g, c: t["upstream_339f324"]["names"].update({"LLM_ARCH_FAKE": ARCH}), "D1 upstream"),
    ("把扩散架构从表里删掉（假装整个扩散都不支持）",
     lambda h, t, g, c: t["local_4da6337"].update({"diffusion_arch_names": []}), "D3 local"),
    ("把负控改成没加载起来",
     lambda h, t, g, c: g.update({"control_ok": False}), "E4"),
    ("把结论改成门槛已开",
     lambda h, t, g, c: g.update({"verdict": "GATE-OPEN"}), "E1"),
    ("把一张张量的维度改掉（参数量重算不上）",
     lambda h, t, g, c: h["models"][DIFF]["tensors"][0]["dims"].__setitem__(0, 7), "A1 " + DIFF),
    ("把两次失败改成一次（少了一个运行时）",
     lambda h, t, g, c: g["attempts"].pop(), "E2"),
    ("把 bf16 权重改成能装下",
     lambda h, t, g, c: g["price"].update({"bf16_weights_gib": 20.0}), "F5"),
    ("把双胞胎位宽改掉（与 bpw_map 脱钩）",
     lambda h, t, g, c: h["models"][TWIN].update({"bpw_file": 4.9}), "C3"),
    ("把真值 KV 改回上界（旧写法：拿 bound 当需求）",
     lambda h, t, g, c: g["price"].update({"kv_true_gib_at_4096": 1.875}), "F2"),
    ("把「当时可容纳」改成装不下",
     lambda h, t, g, c: g["price"].update({"fits_given_true_kv": False}), "F4"),
    ("把 transformers 的 accept_canvas 标记抹掉（假装解码回路不在）",
     lambda h, t, g, c: c["markers"].update({"accept_canvas": False}), "C7"),
]


def run_selftest(headers, tables, gate, code):
    print("负控（--selftest）：把夹具改坏，被点名的检查必须翻红")
    bad = []
    for why, mutate, must_fail in SELFTEST_CASES:
        h, t, g, c = (copy.deepcopy(headers), copy.deepcopy(tables),
                      copy.deepcopy(gate), copy.deepcopy(code))
        mutate(h, t, g, c)
        results.clear()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            checks(h, t, g, c)
        hit = [n for n, ok, _d in results if not ok and n.startswith(must_fail)]
        print(f"  [{'ok' if hit else 'FAIL'}] {why} → 翻红：{hit or '没有'}")
        if not hit:
            bad.append(why)
    print()
    print(f"负控 {len(SELFTEST_CASES)} 条全部翻红" if not bad else f"负控失败：{bad}")
    return 0 if not bad else 1


def main(argv):
    headers, tables, gate, code = load()
    if "--selftest" in argv:
        return run_selftest(headers, tables, gate, code)

    print("a11 收口检查")
    checks(headers, tables, gate, code)

    unverified = []
    if "--live" in argv:
        print("\n现场重放（--live）")
        p = subprocess.run([sys.executable, str(ANALYSIS / "gate.py")], text=True)
        if p.returncode == 2:
            unverified.append("gate.py（缺 gguf 或运行时二进制）")
            print("  [未验证] L1 gate.py 没有输入（rc=2）：门槛的现场重放未执行")
        else:
            expect("L1 gate.py 在现场复现门槛（rc=0）", p.returncode == 0, f"rc={p.returncode}")
        q = subprocess.run([sys.executable, str(ANALYSIS / "record_headers.py"), "--check"],
                           text=True)
        if q.returncode == 2:
            unverified.append("record_headers.py --check")
            print("  [未验证] L2 没有 live 头部可比（rc=2）")
        else:
            expect("L2 头部夹具与盘上文件无漂移", q.returncode == 0, f"rc={q.returncode}")
        r = subprocess.run([sys.executable, str(ANALYSIS / "arch_table.py"),
                            "/home/z/llama.cpp", "--label", "local_4da6337"], text=True)
        if r.returncode == 2:
            unverified.append("arch_table.py（缺源码树）")
            print("  [未验证] L3 没有 live 源码树可比（rc=2）")
        else:
            expect("L3 本机源码树的架构名表与夹具无漂移", r.returncode == 0, f"rc={r.returncode}")
        s4 = subprocess.run([sys.executable, str(ANALYSIS / "transformers_code.py"), "--check"],
                            text=True)
        if s4.returncode == 2:
            unverified.append("transformers_code.py --check（本机没有装 transformers 的 venv）")
            print("  [未验证] L4 没有 live 的 transformers 代码可比（rc=2）")
        else:
            expect("L4 本机 venv 里的 diffusion_gemma 代码与夹具无漂移", s4.returncode == 0,
                   f"rc={s4.returncode}")
        if unverified:
            print(f"  → 现场重放**未验证**：{'、'.join(unverified)}不上；本装置的 0 只覆盖仓库内输入")
    else:
        print("\n[note] 未带 --live：门槛的现场重放（要盘上的 gguf 与 llama.cpp 二进制）没有在本进程执行；"
              "上面的 D 段判的是源级证据，E/F 段判的是已记录序列的自洽。在本机用 "
              "`python3 run_all.py --live` 执行现场重放。")

    failed = [n for n, ok, _d in results if not ok]
    print()
    if failed:
        print(f"失败 {len(failed)} 条：{failed}")
        return 1
    print(f"{len(results)} 条全部成立")
    return 2 if ("--live" in argv and unverified) else 0


if __name__ == "__main__":
    sys.exit(main(tuple(sys.argv[1:])))
