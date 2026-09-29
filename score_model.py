#!/usr/bin/env python3
"""Canonical score formula from the full-data refit (1749 rows, rational/tanh/rational caps).

pred = 1 - exp(-raw)
raw  = exp(linear) * cap_size(size_b) * cap_act(act_ratio) * cap_quant(quant_ratio) * (1 + a_qat*qat)
linear = w[family] + d[dataset] + br*reason_off + bt*temp + btopk*log(top_k)
         + bkvk*k_ratio + bkvv*v_ratio

CV RMSE: checkpoint-held-out 0.1952 | family-held-out 0.2942 | random 0.1935
(ridge reference on the same splits: 0.2097; irreducible floor from unrecorded ctx ~0.088)

Usage:
  from score_model import predict_score
  s = predict_score(size_b=27.0, quant_ratio=0.548, k_ratio=0.53125, v_ratio=0.53125,
                    family="Qwen3.6", dataset="humaneval", reasoning="off")
"""
from __future__ import annotations
import math

CAPS = {'size': 'rational', 'act': 'tanh', 'quant': 'rational'}

def cap_rational(x: float, k: float) -> float:
    return x / (x + k)

def cap_exp(x: float, k: float) -> float:
    return 1.0 - math.exp(-k * x)

def cap_tanh(x: float, k: float) -> float:
    return math.tanh(k * x)

def _cap(kind: str, x: float, k: float) -> float:
    return {"rational": cap_rational, "exp": cap_exp, "tanh": cap_tanh}[kind](x, k)

W_FAMILY = {'DeepSeek-R1-0528-Qwen3': 0.0, 'Dolphin3.0-Llama3.1-abliterated.Q3_K_M': 0.22930209705891197, 'Dolphin3.0-Llama3.1-abliterated.Q4_K_M': 0.10003291496522485, 'Dolphin3.0-Llama3.1-abliterated.Q4_K_S': 0.2346738516520176, 'GLM-4.7': 0.9962943694914469, 'LFM2.5': 0.898490444951165, 'LFM2.5-Instruct': 1.2591104197858984, 'LFM2.5-VL': 1.6420943075469123, 'MiniCPM5': 2.9439518918534864, 'MiniCPM5-Agentic-Tooluse-Nemotron-DPO.Q4_K_M': 1.4249351683304736, 'MiniCPM5-Claude-Opus-Fable5': 3.508849339047653, 'NVIDIA-Nemotron-3': 1.7732830241913276, 'North-1.0': -0.10994544562693032, 'Qwen3.5': 1.7881650259372177, 'Qwen3.5-DeepSeek-V4': 0.7737367893551373, 'Qwen3.6': 1.1813810301191146, 'Qwythos-Claude-Mythos-5': 2.180796309157384, 'Qwythos-v2': 2.135306597741136, 'ThinkingCap-Qwen3.6': 1.1553708756983143, 'functiongemma': -0.0419009255567918, 'gemma-4': 1.363264955998942, 'gemma4-coding': 0.8131335325113308, 'gemma4-v2': 1.075140580595557, 'granite-4.1': 1.957525032489953, 'ornith-1.0': 1.3239424037024694}
D_DATASET = {'humaneval': 0.0, 'mbpp': -0.29838418373914577}
BR = 1.416976
BT = 0.173590
BTOPK = 0.187236
BK_VK = -0.091247
BK_VV = 0.521863
K_SIZE = 16.374961
K_ACT = 26.844543
K_QUANT = 5.541340
A_QAT = 0.043426
MEAN_FAMILY_W = 1.2243

def predict_score(
    *,
    family: str = "unseen",
    dataset: str = "humaneval",
    size_b: float,
    activated_size_b: float | None = None,
    quant_ratio: float,
    k_ratio: float = 0.53125,
    v_ratio: float = 0.53125,
    qat: float = 0.0,
    reasoning: str = "off",
    temp: float = 0.0,
    top_k: float = 40.0,
) -> float:
    """Predicted pass@1_plus on the given benchmark.

    family: use one of ['DeepSeek-R1-0528-Qwen3', 'Dolphin3.0-Llama3.1-abliterated.Q3_K_M', 'Dolphin3.0-Llama3.1-abliterated.Q4_K_M', 'Dolphin3.0-Llama3.1-abliterated.Q4_K_S', 'GLM-4.7', 'LFM2.5'] ...; "unseen" uses the mean
      family weight (best guess for a family not in the fit).
    reasoning: "off" / "auto" (only these two are recorded in the data).
    size_b / quant_ratio / k_ratio / v_ratio: bytes-per-param ratios (fp16=1.0).
    """
    w = W_FAMILY.get(family, MEAN_FAMILY_W)
    d = D_DATASET.get(dataset, 0.0)
    act_ratio = activated_size_b / size_b if activated_size_b else 1.0
    reason_off = 1.0 if reasoning == "off" else 0.0
    linear = (
        w + d + BR * reason_off + BT * temp + BTOPK * math.log(top_k)
        + BK_VK * k_ratio + BK_VV * v_ratio
    )
    linear = max(-40.0, min(18.0, linear))
    raw = (
        math.exp(linear)
        * _cap(CAPS["size"], size_b, K_SIZE)
        * _cap(CAPS["act"], act_ratio, K_ACT)
        * _cap(CAPS["quant"], quant_ratio, K_QUANT)
        * (1.0 + A_QAT * qat)
    )
    return 1.0 - math.exp(-raw)
