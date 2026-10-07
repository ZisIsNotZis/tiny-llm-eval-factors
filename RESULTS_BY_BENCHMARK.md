# 结果按 benchmark 重排

横轴 = **有效 bpw = 8×文件字节/参数量**（解析 GGUF 头），因为标称档位不是比特数（§0）。
代码一律 `multipl-e-raw-greedy-768`；工具调用一律 native-FC；多轮一律 `bfcl-official-multiturn-temp0`。
CI 为 item 级。`[HARNESS]` = 输出格式/方言导致的假 0，不是数据点。

## 0. 横轴修正：标称档位 ≠ 比特数

| 模型 | 标称 | **有效 bpw** | GB |
|---|---|---|---|
| Qwen3.5-0.8B-UD-Q2_K_XL | UD-Q2_K_XL | **4.441** | 0.42 |
| Ternary-Bonsai-1.7B-Q2_0_g64 | UNKNOWN | **2.280** | 0.49 |
| Qwen3.5-0.8B-UD-Q3_K_XL | UD-Q3_K_XL | **5.234** | 0.49 |
| Qwen3.5-2B-UD-IQ2_XXS | UD-IQ2_XXS | **3.266** | 0.77 |
| Qwen3.5-2B-UD-IQ2_M | UD-IQ2_M | **3.655** | 0.86 |
| Qwen3.5-2B-UD-IQ3_XXS | UD-IQ3_XXS | **3.961** | 0.93 |
| Qwen3.5-2B-UD-Q2_K_XL | UD-Q2_K_XL | **4.109** | 0.97 |
| MiniCPM5-2B-Q2_K | Q2_K | **3.224** | 1.01 |
| Ternary-Bonsai-4B-Q2_0_g64 | UNKNOWN | **2.263** | 1.14 |
| Qwen3.5-2B-UD-Q3_K_XL | UD-Q3_K_XL | **4.928** | 1.16 |
| MiniCPM5-2B-Q3_K_M | Q3_K_M | **3.929** | 1.24 |
| Qwen3.5-2B-UD-Q4_K_XL | UD-Q4_K_XL | **5.696** | 1.34 |
| Llama-3.2-3B-Instruct-Q2_K | Q2_K | **3.396** | 1.36 |
| granite-4.1-3b-Q2_K | Q2_K | **3.224** | 1.37 |
| Qwen3.5-2B-UD-Q5_K_XL | UD-Q5_K_XL | **6.235** | 1.47 |
| Phi-4-mini-instruct-Q2_K | Q2_K | **3.509** | 1.68 |
| Llama-3.2-3B-Instruct-Q3_K_M | Q3_K_M | **4.201** | 1.69 |
| granite-4.1-3b-Q3_K_M | Q3_K_M | **4.057** | 1.73 |
| Qwen3.5-4B-UD-Q2_K_XL | UD-Q2_K_XL | **3.692** | 1.94 |
| Qwen3.5-4B-UD-IQ3_XXS | UD-IQ3_XXS | **3.707** | 1.95 |
| granite-4.1-3b-Q4_K_M | Q4_K_M | **4.936** | 2.10 |
| Phi-4-mini-instruct-Q3_K_M | Q3_K_M | **4.416** | 2.12 |
| Ternary-Bonsai-8B-Q2_0_g64 | UNKNOWN | **2.257** | 2.31 |
| gemma-4-E2B-it-UD-Q2_K_XL | UD-Q2_K_XL | **4.138** | 2.40 |
| Qwen3.5-4B-UD-Q3_K_XL | UD-Q3_K_XL | **4.634** | 2.44 |
| NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL | UD-Q2_K_XL | **5.041** | 2.50 |
| NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL | UD-Q3_K_XL | **5.401** | 2.68 |
| gemma-4-E2B-it-UD-Q3_K_XL | UD-Q3_K_XL | **5.033** | 2.92 |
| LFM2.5-8B-A1B-UD-Q2_K_XL | UD-Q2_K_XL | **2.764** | 2.93 |
| LFM2.5-8B-A1B-m55-exq2 | UNKNOWN | **2.918** | 3.09 |
| gemma-4-E4B-it-UD-Q2_K_XL | UD-Q2_K_XL | **3.998** | 3.76 |
| Bonsai-27B-Q1_0 | UNKNOWN | **1.131** | 3.80 |
| LFM2.5-8B-A1B-UD-Q3_K_XL | UD-Q3_K_XL | **3.782** | 4.00 |
| LFM2.5-8B-A1B-m55-Q3_K_M | Q3_K_M | **3.881** | 4.11 |
| Qwen3.5-9B-UD-Q2_K_XL | UD-Q2_K_XL | **3.683** | 4.12 |
| gemma-4-E4B-it-UD-Q3_K_XL | UD-Q3_K_XL | **4.883** | 4.59 |
| gemma-4-12b-it-UD-Q2_K_XL | UD-Q2_K_XL | **3.132** | 4.66 |
| LFM2.5-8B-A1B-m55-exq4 | UNKNOWN | **4.483** | 4.74 |
| Qwen3.5-9B-UD-Q3_K_XL | UD-Q3_K_XL | **4.515** | 5.05 |
| Ornith-1.5-9B-Q4_K_M | Q4_K_M | **5.028** | 5.78 |
| gemma-4-12b-it-UD-Q3_K_XL | UD-Q3_K_XL | **4.046** | 6.02 |
| Ornith-1.5-9B-Q5_K_M | Q5_K_M | **5.778** | 6.64 |
| Ternary-Bonsai-27B-Q2_g64 | UNKNOWN | **2.256** | 7.59 |
| GLM-4.7-Flash-UD-TQ1_0 | UNKNOWN | **2.226** | 8.33 |
| Qwen3.5-35B-A3B-IQ1_M | IQ1_M | **1.995** | 8.64 |
| Qwen3.8-27B-UD-Q2_K_XL | UD-Q2_K_XL | **2.878** | 9.83 |
| gemma-4-26B-A4B-it-UD-Q2_K_XL | UD-Q2_K_XL | **3.344** | 10.55 |
| GLM-4.7-Flash-UD-Q2_K_XL | UD-Q2_K_XL | **3.176** | 11.89 |
| Qwen3.6-35B-A3B-UD-Q2_K_XL | UD-Q2_K_XL | **2.833** | 12.57 |
| gemma-4-26B-A4B-it-UD-Q3_K_XL | UD-Q3_K_XL | **4.092** | 12.91 |
| Qwen3.8-27B-UD-Q3_K_XL | UD-Q3_K_XL | **3.850** | 13.15 |
| GLM-4.7-Flash-UD-Q3_K_XL | UD-Q3_K_XL | **3.682** | 13.78 |
| Qwen3.6-35B-A3B-Q3_K_M | Q3_K_M | **3.857** | 17.12 |
| Qwen3.6-35B-A3B-UD-Q3_K_XL | UD-Q3_K_XL | **3.882** | 17.23 |

同一个 `UD-Q2_K_XL`：LFM2.5-8B-A1B 是 **2.76 bpw**，Nemotron-3-Nano-4B 是 **5.04 bpw**。
下文“Q2→Q3”因此都改读作**实际 bpw 的一段位移**，位移量每对模型不同。

## 1.1 代码（MultiPL-E，raw，greedy）

| 模型 | 档位 | **bpw** | pooled | n | cpp | py | java | js | rs | rb | run_tag |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Bonsai-27B-Q1_0 | UNKNOWN | 1.13 | **0.4596** | 322 | 0.547 | 0.373 | - | - | - | - | m35-sub2bit |
| Qwen3.5-35B-A3B-IQ1_M | IQ1_M | 1.99 | **0.5280** | 322 | 0.491 | 0.565 | - | - | - | - | m35-sub2bit |
| GLM-4.7-Flash-UD-TQ1_0 | UNKNOWN | 2.23 | **0.1770** | 322 | 0.236 | 0.118 | - | - | - | - | m39-glm-ternary |
| Ternary-Bonsai-27B-Q2_g64 | UNKNOWN | 2.26 | **0.7298** | 322 | 0.696 | 0.764 | - | - | - | - | m21-bonsai-ternary |
| Ternary-Bonsai-8B-Q2_0_g64 | UNKNOWN | 2.26 | **0.5839** | 322 | 0.553 | 0.615 | - | - | - | - | m24-bonsai-series |
| Ternary-Bonsai-4B-Q2_0_g64 | UNKNOWN | 2.26 | **0.5839** | 322 | 0.491 | 0.677 | - | - | - | - | m35-sub2bit |
| Ternary-Bonsai-1.7B-Q2_0_g64 | UNKNOWN | 2.28 | **0.3540** | 322 | 0.292 | 0.416 | - | - | - | - | m24-bonsai-series |
| LFM2.5-8B-A1B-UD-Q2_K_XL | UD-Q2_K_XL | 2.76 | **0.0905** | 641 | 0.161 | 0.062 | 0.070 | 0.068 | - | - | m10-family-ladder |
| Qwen3.6-35B-A3B-UD-Q2_K_XL | UD-Q2_K_XL | 2.83 | **0.7019** | 322 | 0.708 | 0.696 | - | - | - | - | m6-family-ladder |
| Qwen3.8-27B-UD-Q2_K_XL | UD-Q2_K_XL | 2.88 | **0.7516** | 322 | 0.758 | 0.745 | - | - | - | - | m10-family-ladder |
| LFM2.5-8B-A1B-m55-exq2 | UNKNOWN | 2.92 | **0.1025** | 322 | 0.137 | 0.068 | - | - | - | - | m55-expertwise |
| gemma-4-12b-it-UD-Q2_K_XL | UD-Q2_K_XL | 3.13 | **0.0016** | 635 | - | - | 0.000 | 0.000 | 0.006 | 0.000 | m51-gemma-java-js |
| GLM-4.7-Flash-UD-Q2_K_XL | UD-Q2_K_XL | 3.18 | **0.4099** | 322 | 0.472 | 0.348 | - | - | - | - | m39-glm-ternary |
| MiniCPM5-2B-Q2_K | Q2_K | 3.22 | **0.0745** | 322 | 0.062 | 0.087 | - | - | - | - | m10-family-ladder |
| granite-4.1-3b-Q2_K | Q2_K | 3.22 | **0.0476** | 483 | 0.037 | 0.056 | - | 0.050 | - | - | m5-family-ladder |
| Qwen3.5-2B-UD-IQ2_XXS | UD-IQ2_XXS | 3.27 | **0.0062** | 161 | 0.006 | - | - | - | - | - | m3-quant-ladder |
| gemma-4-26B-A4B-it-UD-Q2_K_XL | UD-Q2_K_XL | 3.34 | **0.0435** | 322 | 0.056 | 0.031 | - | - | - | - | m10-family-ladder |
| Llama-3.2-3B-Instruct-Q2_K | Q2_K | 3.40 | **0.2640** | 322 | 0.230 | 0.298 | - | - | - | - | m58-llama32-family |
| Phi-4-mini-instruct-Q2_K | Q2_K | 3.51 | **0.0217** | 322 | 0.019 | 0.025 | - | - | - | - | m59-phi4mini-family |
| Qwen3.5-2B-UD-IQ2_M | UD-IQ2_M | 3.66 | **0.1387** | 483 | 0.112 | 0.161 | - | 0.143 | - | - | m3-quant-ladder |
| GLM-4.7-Flash-UD-Q3_K_XL | UD-Q3_K_XL | 3.68 | **0.5373** | 322 | 0.584 | 0.491 | - | - | - | - | m33-family-breadth |
| Qwen3.5-9B-UD-Q2_K_XL | UD-Q2_K_XL | 3.68 | **0.4286** | 483 | 0.435 | 0.348 | - | 0.503 | - | - | w2-scale-ladder |
| Qwen3.5-4B-UD-Q2_K_XL | UD-Q2_K_XL | 3.69 | **0.3145** | 957 | 0.342 | 0.354 | 0.323 | 0.342 | 0.258 | 0.267 | w2-scale-ladder |
| Qwen3.5-4B-UD-IQ3_XXS | UD-IQ3_XXS | 3.71 | **0.3944** | 322 | 0.379 | 0.410 | - | - | - | - | m23-scheme-iqk |
| LFM2.5-8B-A1B-UD-Q3_K_XL | UD-Q3_K_XL | 3.78 | **0.0858** | 641 | 0.143 | 0.037 | 0.051 | 0.112 | - | - | m10-family-ladder |
| Qwen3.8-27B-UD-Q3_K_XL | UD-Q3_K_XL | 3.85 | **0.7702** | 322 | 0.807 | 0.733 | - | - | - | - | m10-family-ladder |
| Qwen3.6-35B-A3B-Q3_K_M | Q3_K_M | 3.86 | **0.7484** | 322 | 0.758 | 0.739 | - | - | - | - | m25-vendor |
| LFM2.5-8B-A1B-m55-Q3_K_M | Q3_K_M | 3.88 | **0.0807** | 322 | 0.130 | 0.031 | - | - | - | - | m55-expertwise |
| Qwen3.6-35B-A3B-UD-Q3_K_XL | UD-Q3_K_XL | 3.88 | **0.7391** | 322 | 0.720 | 0.758 | - | - | - | - | m6-family-ladder |
| MiniCPM5-2B-Q3_K_M | Q3_K_M | 3.93 | **0.3882** | 322 | 0.373 | 0.404 | - | - | - | - | m10-family-ladder |
| Qwen3.5-2B-UD-IQ3_XXS | UD-IQ3_XXS | 3.96 | **0.1894** | 322 | 0.180 | 0.199 | - | - | - | - | m23-scheme-iqk |
| gemma-4-E4B-it-UD-Q2_K_XL | UD-Q2_K_XL | 4.00 | **0.3913** | 483 | 0.472 | 0.497 | - | 0.205 | - | - | m5-family-ladder |
| gemma-4-12b-it-UD-Q3_K_XL | UD-Q3_K_XL | 4.05 | **0.0063** | 635 | - | - | 0.025 | 0.000 | 0.000 | 0.000 | m51-gemma-java-js |
| granite-4.1-3b-Q3_K_M | Q3_K_M | 4.06 | **0.3913** | 483 | 0.478 | 0.242 | - | 0.453 | - | - | m5-family-ladder |
| gemma-4-26B-A4B-it-UD-Q3_K_XL | UD-Q3_K_XL | 4.09 | **0.0342** | 322 | 0.025 | 0.043 | - | - | - | - | m10-family-ladder |
| Qwen3.5-2B-UD-Q2_K_XL | UD-Q2_K_XL | 4.11 | **0.0920** | 957 | 0.112 | 0.137 | 0.120 | 0.112 | 0.065 | 0.006 | m3-quant-ladder |
| gemma-4-E2B-it-UD-Q2_K_XL | UD-Q2_K_XL | 4.14 | **0.2008** | 483 | 0.298 | 0.186 | - | 0.118 | - | - | m5-family-ladder |
| Llama-3.2-3B-Instruct-Q3_K_M | Q3_K_M | 4.20 | **0.4224** | 322 | 0.348 | 0.497 | - | - | - | - | m58-llama32-family |
| Phi-4-mini-instruct-Q3_K_M | Q3_K_M | 4.42 | **0.4068** | 322 | 0.348 | 0.466 | - | - | - | - | m59-phi4mini-family |
| Qwen3.5-0.8B-UD-Q2_K_XL | UD-Q2_K_XL | 4.44 | **0.0452** | 641 | 0.043 | 0.068 | 0.019 | 0.050 | - | - | m6-family-ladder |
| LFM2.5-8B-A1B-m55-exq4 | UNKNOWN | 4.48 | **0.0683** | 322 | 0.087 | 0.050 | - | - | - | - | m55-expertwise |
| Qwen3.5-9B-UD-Q3_K_XL | UD-Q3_K_XL | 4.52 | **0.5714** | 483 | 0.584 | 0.522 | - | 0.609 | - | - | w2-scale-ladder |
| Qwen3.5-4B-UD-Q3_K_XL | UD-Q3_K_XL | 4.63 | **0.4566** | 957 | 0.453 | 0.503 | 0.487 | 0.534 | 0.413 | 0.348 | w2-scale-ladder |
| gemma-4-E4B-it-UD-Q3_K_XL | UD-Q3_K_XL | 4.88 | **0.6128** | 483 | 0.739 | 0.640 | - | 0.460 | - | - | m5-family-ladder |
| Qwen3.5-2B-UD-Q3_K_XL | UD-Q3_K_XL | 4.93 | **0.2184** | 957 | 0.242 | 0.267 | 0.215 | 0.317 | 0.161 | 0.106 | m3-quant-ladder |
| granite-4.1-3b-Q4_K_M | Q4_K_M | 4.94 | **0.4379** | 322 | 0.571 | 0.304 | - | - | - | - | m10-granite-q34 |
| Ornith-1.5-9B-Q4_K_M | Q4_K_M | 5.03 | **0.5016** | 638 | 0.609 | 0.422 | - | - | 0.523 | 0.453 | m10-family-ladder |
| gemma-4-E2B-it-UD-Q3_K_XL | UD-Q3_K_XL | 5.03 | **0.4161** | 483 | 0.534 | 0.348 | - | 0.366 | - | - | m5-family-ladder |
| NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL | UD-Q2_K_XL | 5.04 | **0.4197** | 641 | 0.578 | 0.646 | 0.373 | 0.081 | - | - | m10-family-ladder |
| Qwen3.5-0.8B-UD-Q3_K_XL | UD-Q3_K_XL | 5.23 | **0.1061** | 641 | 0.068 | 0.130 | 0.095 | 0.130 | - | - | m6-family-ladder |
| NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL | UD-Q3_K_XL | 5.40 | **0.4540** | 641 | 0.602 | 0.658 | 0.405 | 0.149 | - | - | m10-family-ladder |
| Qwen3.5-2B-UD-Q4_K_XL | UD-Q4_K_XL | 5.70 | **0.2836** | 483 | 0.230 | 0.273 | - | 0.348 | - | - | w1-repeat |
| Ornith-1.5-9B-Q5_K_M | Q5_K_M | 5.78 | **0.5266** | 638 | 0.621 | 0.472 | - | - | 0.548 | 0.466 | m10-family-ladder |
| Qwen3.5-2B-UD-Q5_K_XL | UD-Q5_K_XL | 6.24 | **0.2774** | 483 | 0.261 | 0.280 | - | 0.292 | - | - | m3-quant-ladder |

### 1.1b 代码上 Q2→Q3 这一步（item 级 CI，按真实 bpw 位移）

| 模型 | bpw 位移 | Δpooled | 95% CI | 显著 | run_tag |
|---|---|---|---|---|---|
| GLM-4.7-Flash-UD-Q2_K_XL | 3.18→3.68 (+0.51) | +0.1273 | [+0.0508, +0.2038] | **是** | m39-glm-ternary |
| LFM2.5-8B-A1B-UD-Q2_K_XL | 2.76→3.78 (+1.02) | -0.0047 | [-0.0357, +0.0264] | 否 | m10-family-ladder |
| Llama-3.2-3B-Instruct-Q2_K | 3.40→4.20 (+0.80) | +0.1584 | [+0.0861, +0.2307] | **是** | m58-llama32-family |
| MiniCPM5-2B-Q2_K | 3.22→3.93 (+0.70) | +0.3137 | [+0.2532, +0.3741] | **是** | m10-family-ladder |
| NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL | 5.04→5.40 (+0.36) | +0.0343 | [-0.0199, +0.0886] | 否 | m10-family-ladder |
| Phi-4-mini-instruct-Q2_K | 3.51→4.42 (+0.91) | +0.3851 | [+0.3291, +0.4411] | **是** | m59-phi4mini-family |
| Qwen3.5-0.8B-UD-Q2_K_XL | 4.44→5.23 (+0.79) | +0.0608 | [+0.0321, +0.0896] | **是** | m6-family-ladder |
| Qwen3.5-2B-UD-Q2_K_XL | 4.11→4.93 (+0.82) | +0.1264 | [+0.0945, +0.1584] | **是** | m3-quant-ladder |
| Qwen3.5-4B-UD-Q2_K_XL | 3.69→4.63 (+0.94) | +0.1421 | [+0.0990, +0.1853] | **是** | w2-scale-ladder |
| Qwen3.5-9B-UD-Q2_K_XL | 3.68→4.52 (+0.83) | +0.1429 | [+0.0804, +0.2053] | **是** | w2-scale-ladder |
| Qwen3.6-35B-A3B-UD-Q2_K_XL | 2.83→3.88 (+1.05) | +0.0373 | [-0.0320, +0.1065] | 否 | m6-family-ladder |
| Qwen3.8-27B-UD-Q2_K_XL | 2.88→3.85 (+0.97) | +0.0186 | [-0.0472, +0.0845] | 否 | m10-family-ladder |
| gemma-4-12b-it-UD-Q2_K_XL | 3.13→4.05 (+0.91) | +0.0047 | [-0.0022, +0.0116] | 否 | m51-gemma-java-js |
| gemma-4-26B-A4B-it-UD-Q2_K_XL | 3.34→4.09 (+0.75) | -0.0093 | [-0.0391, +0.0205] | 否 | m10-family-ladder |
| gemma-4-E2B-it-UD-Q2_K_XL | 4.14→5.03 (+0.90) | +0.2153 | [+0.1587, +0.2720] | **是** | m5-family-ladder |
| gemma-4-E4B-it-UD-Q2_K_XL | 4.00→4.88 (+0.88) | +0.2215 | [+0.1600, +0.2830] | **是** | m5-family-ladder |
| granite-4.1-3b-Q2_K | 3.22→4.06 (+0.83) | +0.3437 | [+0.2962, +0.3912] | **是** | m5-family-ladder |

## 1.2 工具调用·单轮（BFCL v4，native-FC）

| 模型 | 档位 | **bpw** | irrelev | multiple | parallel | par_multi | simple_py | 均值 |
|---|---|---|---|---|---|---|---|---|
| Ternary-Bonsai-27B-Q2_g64 | UNKNOWN | 2.26 | 0.7667 | 0.5950 | 0.7750 | 0.7150 | 0.6750 | **0.7053** |
| granite-4.1-3b-Q2_K | Q2_K | 3.22 | 0.9875 | 0.0200 | 0.0100 | 0.0100 | 0.0150 | **0.2085** |
| Qwen3.5-4B-UD-Q2_K_XL | UD-Q2_K_XL | 3.69 | 0.9083 | 0.5750 | 0.4950 | 0.4900 | 0.5800 | **0.6097** |
| gemma-4-E4B-it-UD-Q2_K_XL | UD-Q2_K_XL | 4.00 | 0.8500 | 0.6100 | 0.7050 | 0.6700 | 0.6225 | **0.6915** |
| granite-4.1-3b-Q3_K_M | Q3_K_M | 4.06 | 0.3458 | 0.5850 | 0.7000 | 0.5750 | 0.6600 | **0.5732** |
| Qwen3.5-2B-UD-Q2_K_XL | UD-Q2_K_XL | 4.11 | 0.8458 | 0.1750 | 0.0350 | 0.1950 | 0.2175 | **0.2937** |
| gemma-4-E2B-it-UD-Q2_K_XL | UD-Q2_K_XL | 4.14 | 0.7458 | 0.5800 | 0.6050 | 0.6350 | 0.5725 | **0.6277** |
| Qwen3.5-4B-UD-Q3_K_XL | UD-Q3_K_XL | 4.63 | 0.7792 | 0.6250 | 0.7150 | 0.6900 | 0.6600 | **0.6938** |
| gemma-4-E4B-it-UD-Q3_K_XL | UD-Q3_K_XL | 4.88 | 0.8792 | 0.5950 | 0.7400 | 0.6800 | 0.6200 | **0.7028** |
| Qwen3.5-2B-UD-Q3_K_XL | UD-Q3_K_XL | 4.93 | 0.9167 | 0.5400 | 0.2350 | 0.2250 | 0.5050 | **0.4843** |
| gemma-4-E2B-it-UD-Q3_K_XL | UD-Q3_K_XL | 5.03 | 0.8167 | 0.5800 | 0.7050 | 0.6450 | 0.5975 | **0.6688** |

`[HARNESS]` granite-4.1-3b 的 Q2 行：live_parallel / live_parallel_multiple 恰 0.0000，
且 4 个需发调用的类别全 ≤0.02，而 irrelevance 0.99 —— native-FC 方言不匹配，非 Q2 低分证据。

## 1.3 Agentic·多轮（BFCL-MT，temp0）

| 模型 | 档位 | **bpw** | base | long_ctx | miss_func | miss_param |
|---|---|---|---|---|---|---|
| Ternary-Bonsai-27B-Q2_g64 | UNKNOWN | 2.26 | 0.6975 | - | 0.5150 | 0.4350 |
| Qwen3.6-35B-A3B-UD-Q2_K_XL | UD-Q2_K_XL | 2.83 | 0.6000 | - | - | - |
| Qwen3.5-9B-UD-Q2_K_XL | UD-Q2_K_XL | 3.68 | 0.4900 | - | - | - |
| Qwen3.5-4B-UD-Q2_K_XL | UD-Q2_K_XL | 3.69 | 0.3850 | 0.3800 | - | - |
| Qwen3.6-35B-A3B-UD-Q3_K_XL | UD-Q3_K_XL | 3.88 | 0.6750 | - | - | - |
| granite-4.1-3b-Q3_K_M | Q3_K_M | 4.06 | 0.1750 | - | - | - |
| Qwen3.5-2B-UD-Q2_K_XL | UD-Q2_K_XL | 4.11 | 0.0250 | 0.0050 | 0.0050 | 0.0050 |
| Qwen3.5-9B-UD-Q3_K_XL | UD-Q3_K_XL | 4.52 | 0.6500 | - | - | - |
| Qwen3.5-4B-UD-Q3_K_XL | UD-Q3_K_XL | 4.63 | 0.5350 | 0.5050 | - | - |
| Qwen3.5-2B-UD-Q3_K_XL | UD-Q3_K_XL | 4.93 | 0.1850 | 0.1113 | 0.0800 | 0.1050 |

**多轮是量化最敏感的 benchmark**：2B 在 Q2 时 base/long_ctx/miss_func/miss_param 全部 **0.025/0.005/0.005/0.005**，
Q3 恢复到 0.185/0.111/0.080/0.105 —— 每个类别各自的天花板。
对比：同一模型在**代码**上 Q2→Q3 是 0.092→0.218（也有损但没归零）。

## 1.4 PPL（同横轴，与跑分对照）

| 模型 | 档位阶 | ppl | 代码 pass@1 |
|---|---|---|---|
| Qwen3.5-2B | 2 | 1.9044 | 0.1201 |
| Qwen3.5-2B | 2 | 1.9665 | 0.1387 |
| Qwen3.5-2B | 2 | 2.3317 | 0.0062 |
| Qwen3.5-2B | 3 | 1.8059 | 0.2754 |
| Qwen3.5-2B | 4 | 1.7834 | 0.2836 |
| Qwen3.5-2B | 5 | 1.7788 | 0.2774 |
| Qwen3.5-0.8B | 2 | 2.2559 | 0.0451 |
| Qwen3.5-0.8B | 3 | 1.9677 | 0.1060 |
| Qwen3.5-0.8B | 4 | 1.9343 | - |
| Qwen3.5-0.8B | 5 | 1.9264 | - |
| Qwen3.5-4B | 2 | 1.7446 | 0.3142 |
| Qwen3.5-4B | 3 | 1.6872 | 0.4565 |
| Qwen3.5-4B | 4 | 1.6685 | - |
| Qwen3.5-4B | 5 | 1.6625 | - |
| gemma-4-E2B-it | 2 | 3.1067 | 0.2008 |
| gemma-4-E2B-it | 3 | 3.5378 | 0.4161 |
| granite-4.1-3b | 2 | 2.4728 | 0.0476 |
| granite-4.1-3b | 3 | 2.0526 | 0.3789 |
| granite-4.1-3b | 4 | 1.7657 | 0.4379 |

## 2. Ternary / 亚 2-bit（单列，与常规量化放同一 bpw 轴）

| 模型 | **bpw** | 代码 pooled | MT base | MT miss_func | MT miss_param | BFCL 单轮均值 |
|---|---|---|---|---|---|---|
| Ternary-Bonsai-1.7B-Q2_0_g64 | **2.280** | 0.3540 | - | - | - | - |
| Ternary-Bonsai-4B-Q2_0_g64 | **2.263** | 0.5839 | - | - | - | - |
| Ternary-Bonsai-8B-Q2_0_g64 | **2.257** | 0.5839 | - | - | - | - |
| Ternary-Bonsai-27B-Q2_g64 | **2.256** | 0.7298 | 0.6975 | 0.5150 | 0.4350 | 0.7053 |
| Bonsai-27B-Q1_0 | **1.131** | 0.4596 | - | - | - | - |
| Qwen3.5-35B-A3B-IQ1_M | **1.995** | 0.5280 | - | - | - | - |

**Ternary-Bonsai-27B 在 2.26 bpw 上，多轮/工具调用全面达到或超过 3.7–5.4 bpw 的常规量化**；
但同一族的 `GLM-4.7-Flash-UD-TQ1_0`（2.23 bpw）在代码上只有它自己 Q2 的一半 → **配方特异**。

## 3. 量化方案：迭代/imatrix(IQ) vs K-quant vs 厂商标签

核心问题：**在真实 bpw / 真实文件大小相同时，换方案有没有用？**

| 对比 | 基准 | 配置A | bpw | 配置B | bpw | **Δ = A−B** | 95% CI | 显著 | run_tag |
|---|---|---|---|---|---|---|---|---|---|
| Qwen3.5-2B imatrix vs K | 代码(cpp/py) | UD-IQ3_XXS | 3.96 | UD-Q2_K_XL | 4.11 | +0.0652 | [+0.0093, +0.1212] | **是** | m50-imatrix-vs-k |
| Qwen3.5-4B imatrix vs K | 代码(cpp/py) | UD-IQ3_XXS | 3.71 | UD-Q2_K_XL | 3.69 | +0.0466 | [-0.0280, +0.1211] | 否 | m50-imatrix-vs-k |
| 厂商 Q3_K_M vs UD-Q3_K_XL | 代码(cpp/py) | Q3_K_M | 3.86 | UD-Q3_K_XL | 3.88 | -0.0093 | [-0.0767, +0.0581] | 否 | m37-vendor-matched-size |

**方案 > 比特数的证据比原先报告的弱**：把语言集对齐后（cpp+py 两模型都是 322 题），
- 2B：IQ3_XXS(3.96bpw) 比 Q2_K_XL(4.11bpw) **高 +0.065，CI[+0.009,+0.121]，显著** —— 更小且更好；
- 4B：同方向 (+0.047) 但 **CI[−0.028,+0.121] 跨 0，不显著**。
原先“4/4 单元格全胜”是**按符号一致**记的，不是逐格显著；此处更正为 **2B 显著、4B 仅方向一致**。
**厂商标签本身无效**（Q3_K_M vs UD-Q3_K_XL 差 0.009，CI 跨 0）。
专家感知混合精度（m55，LFM2.5-8B-A1B）：专家 Q2_K+其余 Q5_K_M = **2.92 bpw / 0.1025**，
均匀 Q3_K_M = 3.88 bpw / 0.0807 → 更小且名义更好，但 Δ=+0.022 CI[-0.023,+0.066] **不显著**。

## 4. 模型规模 × benchmark（固定档位）

| benchmark | 档位阶 | 模型（按参数量升序）| 参数量 B | **bpw** | 分数 |
|---|---|---|---|---|---|
| 代码 | 混杂 | Qwen3.5-0.8B-UD-Q2_K_XL | 0.75 | 4.44 | 0.0451 |
| 代码 | 混杂 | Qwen3.5-0.8B-UD-Q3_K_XL | 0.75 | 5.23 | 0.1060 |
| 代码 | 混杂 | Ternary-Bonsai-1.7B-Q2_0_g64 | 1.72 | 2.28 | 0.3540 |
| 代码 | 混杂 | Qwen3.5-2B-UD-IQ2_M | 1.88 | 3.66 | 0.1387 |
| 代码 | 混杂 | Qwen3.5-2B-UD-IQ2_XXS | 1.88 | 3.27 | 0.0062 |
| 代码 | 混杂 | Qwen3.5-2B-UD-IQ3_XXS | 1.88 | 3.96 | 0.1894 |
| 代码 | 混杂 | Qwen3.5-2B-UD-Q2_K_XL | 1.88 | 4.11 | 0.0956 |
| 代码 | 混杂 | Qwen3.5-2B-UD-Q3_K_XL | 1.88 | 4.93 | 0.2165 |
| 代码 | 混杂 | Qwen3.5-2B-UD-Q4_K_XL | 1.88 | 5.70 | 0.2836 |
| 代码 | 混杂 | Qwen3.5-2B-UD-Q5_K_XL | 1.88 | 6.24 | 0.2774 |
| 代码 | 混杂 | MiniCPM5-2B-Q2_K | 2.52 | 3.22 | 0.0745 |
| 代码 | 混杂 | MiniCPM5-2B-Q3_K_M | 2.52 | 3.93 | 0.3882 |
| 代码 | 混杂 | Llama-3.2-3B-Instruct-Q2_K | 3.21 | 3.40 | 0.2640 |
| 代码 | 混杂 | Llama-3.2-3B-Instruct-Q3_K_M | 3.21 | 4.20 | 0.4224 |
| 代码 | 混杂 | granite-4.1-3b-Q2_K | 3.40 | 3.22 | 0.0476 |
| 代码 | 混杂 | granite-4.1-3b-Q3_K_M | 3.40 | 4.06 | 0.3789 |
| 代码 | 混杂 | granite-4.1-3b-Q4_K_M | 3.40 | 4.94 | 0.4379 |
| 代码 | 混杂 | Phi-4-mini-instruct-Q2_K | 3.84 | 3.51 | 0.0217 |
| 代码 | 混杂 | Phi-4-mini-instruct-Q3_K_M | 3.84 | 4.42 | 0.4068 |
| 代码 | 混杂 | NVIDIA-Nemotron-3-Nano-4B-UD-Q2_K_XL | 3.97 | 5.04 | 0.4194 |
| 代码 | 混杂 | NVIDIA-Nemotron-3-Nano-4B-UD-Q3_K_XL | 3.97 | 5.40 | 0.6108 |
| 代码 | 混杂 | Ternary-Bonsai-4B-Q2_0_g64 | 4.02 | 2.26 | 0.5839 |
| 代码 | 混杂 | Qwen3.5-4B-UD-IQ3_XXS | 4.21 | 3.71 | 0.3944 |
| 代码 | 混杂 | Qwen3.5-4B-UD-Q2_K_XL | 4.21 | 3.69 | 0.3387 |
| 代码 | 混杂 | Qwen3.5-4B-UD-Q3_K_XL | 4.21 | 4.63 | 0.4565 |
| 代码 | 混杂 | gemma-4-E2B-it-UD-Q2_K_XL | 4.65 | 4.14 | 0.2008 |
| 代码 | 混杂 | gemma-4-E2B-it-UD-Q3_K_XL | 4.65 | 5.03 | 0.4161 |
| 代码 | 混杂 | gemma-4-E4B-it-UD-Q2_K_XL | 7.52 | 4.00 | 0.3913 |
| 代码 | 混杂 | gemma-4-E4B-it-UD-Q3_K_XL | 7.52 | 4.88 | 0.6128 |
| 代码 | 混杂 | Ternary-Bonsai-8B-Q2_0_g64 | 8.19 | 2.26 | 0.5839 |
| 代码 | 混杂 | LFM2.5-8B-A1B-UD-Q2_K_XL | 8.47 | 2.76 | 0.1082 |
| 代码 | 混杂 | LFM2.5-8B-A1B-UD-Q3_K_XL | 8.47 | 3.78 | 0.0893 |
| 代码 | 混杂 | LFM2.5-8B-A1B-m55-Q3_K_M | 8.47 | 3.88 | 0.0807 |
| 代码 | 混杂 | LFM2.5-8B-A1B-m55-exq2 | 8.47 | 2.92 | 0.1025 |
| 代码 | 混杂 | LFM2.5-8B-A1B-m55-exq4 | 8.47 | 4.48 | 0.0683 |
| 代码 | 混杂 | Qwen3.5-9B-UD-Q2_K_XL | 8.95 | 3.68 | 0.4286 |
| 代码 | 混杂 | Qwen3.5-9B-UD-Q3_K_XL | 8.95 | 4.52 | 0.5714 |
| 代码 | 混杂 | Ornith-1.5-9B-Q4_K_M | 9.20 | 5.03 | 0.5140 |
| 代码 | 混杂 | Ornith-1.5-9B-Q5_K_M | 9.20 | 5.78 | 0.5268 |
| 代码 | 混杂 | gemma-4-12b-it-UD-Q2_K_XL | 11.91 | 3.13 | 0.0014 |
| 代码 | 混杂 | gemma-4-12b-it-UD-Q3_K_XL | 11.91 | 4.05 | 0.0072 |
| 代码 | 混杂 | gemma-4-26B-A4B-it-UD-Q2_K_XL | 25.23 | 3.34 | 0.0435 |
| 代码 | 混杂 | gemma-4-26B-A4B-it-UD-Q3_K_XL | 25.23 | 4.09 | 0.0342 |
| 代码 | 混杂 | Bonsai-27B-Q1_0 | 26.90 | 1.13 | 0.4596 |
| 代码 | 混杂 | Ternary-Bonsai-27B-Q2_g64 | 26.90 | 2.26 | 0.7298 |
| 代码 | 混杂 | Qwen3.8-27B-UD-Q2_K_XL | 27.32 | 2.88 | 0.7516 |
| 代码 | 混杂 | Qwen3.8-27B-UD-Q3_K_XL | 27.32 | 3.85 | 0.7702 |
| 代码 | 混杂 | GLM-4.7-Flash-UD-Q2_K_XL | 29.94 | 3.18 | 0.4099 |
| 代码 | 混杂 | GLM-4.7-Flash-UD-Q3_K_XL | 29.94 | 3.68 | 0.5373 |
| 代码 | 混杂 | GLM-4.7-Flash-UD-TQ1_0 | 29.94 | 2.23 | 0.1770 |
| 代码 | 混杂 | Qwen3.5-35B-A3B-IQ1_M | 34.66 | 1.99 | 0.5280 |
| 代码 | 混杂 | Qwen3.6-35B-A3B-UD-Q2_K_XL | 35.51 | 2.83 | 0.7019 |
| 代码 | 混杂 | Qwen3.6-35B-A3B-UD-Q3_K_XL | 35.51 | 3.88 | 0.7391 |
| 代码 | 混杂 | Qwen3.6-35B-A3B-Q3_K_M | 35.51 | 3.86 | 0.7484 |
| BFCL单轮 | 混杂 | Qwen3.5-2B-UD-Q2_K_XL | 1.88 | 4.11 | 0.2985 |
| BFCL单轮 | 混杂 | Qwen3.5-2B-UD-Q3_K_XL | 1.88 | 4.93 | 0.4870 |
| BFCL单轮 | 混杂 | granite-4.1-3b-Q2_K | 3.40 | 3.22 | 0.1972 |
| BFCL单轮 | 混杂 | granite-4.1-3b-Q3_K_M | 3.40 | 4.06 | 0.5154 |
| BFCL单轮 | 混杂 | Qwen3.5-4B-UD-Q2_K_XL | 4.21 | 3.69 | 0.6097 |
| BFCL单轮 | 混杂 | Qwen3.5-4B-UD-Q3_K_XL | 4.21 | 4.63 | 0.6938 |
| BFCL单轮 | 混杂 | gemma-4-E2B-it-UD-Q2_K_XL | 4.65 | 4.14 | 0.6277 |
| BFCL单轮 | 混杂 | gemma-4-E2B-it-UD-Q3_K_XL | 4.65 | 5.03 | 0.6688 |
| BFCL单轮 | 混杂 | gemma-4-E4B-it-UD-Q2_K_XL | 7.52 | 4.00 | 0.6915 |
| BFCL单轮 | 混杂 | gemma-4-E4B-it-UD-Q3_K_XL | 7.52 | 4.88 | 0.7028 |
| BFCL单轮 | 混杂 | Ternary-Bonsai-27B-Q2_g64 | 26.90 | 2.26 | 0.7053 |
| 多轮base | 混杂 | Qwen3.5-2B-UD-Q2_K_XL | 1.88 | 4.11 | 0.0250 |
| 多轮base | 混杂 | Qwen3.5-2B-UD-Q3_K_XL | 1.88 | 4.93 | 0.1850 |
| 多轮base | 混杂 | granite-4.1-3b-Q3_K_M | 3.40 | 4.06 | 0.1750 |
| 多轮base | 混杂 | Qwen3.5-4B-UD-Q2_K_XL | 4.21 | 3.69 | 0.3850 |
| 多轮base | 混杂 | Qwen3.5-4B-UD-Q3_K_XL | 4.21 | 4.63 | 0.5350 |
| 多轮base | 混杂 | Qwen3.5-9B-UD-Q2_K_XL | 8.95 | 3.68 | 0.4900 |
| 多轮base | 混杂 | Qwen3.5-9B-UD-Q3_K_XL | 8.95 | 4.52 | 0.6500 |
| 多轮base | 混杂 | Ternary-Bonsai-27B-Q2_g64 | 26.90 | 2.26 | 0.6975 |
| 多轮base | 混杂 | Qwen3.6-35B-A3B-UD-Q2_K_XL | 35.51 | 2.83 | 0.6000 |
| 多轮base | 混杂 | Qwen3.6-35B-A3B-UD-Q3_K_XL | 35.51 | 3.88 | 0.6750 |

**规模与分数在代码上基本单调，但有两个明确反例**：gemma-4-26B-A4B（25.2B，Q2/Q3 只有 0.04）
和 gemma-4-12b-it（11.9B，0.00~0.006，`[HARNESS]`）在**参数更多时分数低于 3B 的 Llama/granite**。
所以“越大越好”在**同族内**成立，跨族不成立——训练质量与分词器的影响大于参数量。

## 5. KV 量化 × benchmark

数据只有 **Qwen3.5-2B / 代码 / cpp** 一格（m30），**没有任何其他 benchmark 的 KV 数据**——
因此**不能**对 KV 做跨 benchmark 断言，以下是全部证据：

| ctx | KV f16/f16 | f16/q8_0 | q8_0/f16 | q8_0/q8_0 |
|---|---|---|---|---|
| 2048 | 0.0667 | 0.0667 | 0.0667 | 0.0667 |
| 16384 | 0.0000 | 0.0000 | 0.0167 | 0.0167 |
| 49152 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

**同一 ctx 下 4 种 KV 配置几乎逐格相同** → KV 量化无信号。分数真正崩掉来自 **ctx/padding**
（2048→16384 就 0.067→0.000）。注意每格 **n=1**，证据强度弱。prompt 被填充到 ~15k/48k token 本身就会毁掉答案。

flash-attn（m44）：Q3 上 `faon_f16` 与 `faoff_f16` **逐字节相同**，是**非操作**；Q2 上才不同——
所以 m29 的 `-fa` “null”是**非测量**，不是结果。

## 6. 采样参数 × benchmark

数据只有 **Qwen3.5-2B / 代码（cpp+py）**——同样**无法**跨 benchmark 断言。

| 轴 | 取值 | cpp | py | run_tag |
|---|---|---|---|---|
| temp | 0.0 | 0.1118 | 0.1366 | m27-sampling |
| temp | 0.3 | 0.1718 | 0.2484 | m27-sampling |
| temp | 0.6 | 0.1511 | 0.2277 | m27-sampling |
| top_k | 1 | 0.1946 | 0.2257 | m31-topk |
| top_k | 20 | 0.1718 | 0.2484 | m31-topk |
| top_k | 40 | 0.1718 | 0.2484 | m31-topk |
| top_k | 64 | 0.1718 | 0.2484 | m31-topk |
| top_k | 200 | 0.1718 | 0.2484 | m31-topk |

**top_k ≥ 20 完全相同（0.1718/0.2484，逐格一致）**，只有 K=1 不同（cpp 更高、py 更低，双向）；
温度改变绝对分数（0.3 最好）但不改变量化结论。**两者都只在代码上测过。**

