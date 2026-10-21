# unsloth/Qwen3.5-2B-GGUF model card — sampling recommendation excerpt

retrieved: 2026-10-21T00:01:40Z
source url: https://hf-mirror.com/unsloth/Qwen3.5-2B-GGUF/raw/main/README.md
byte size: 64059
sha256: d6507c9243588d5526ceb08840ebd759b0d05aeb96c8aeb42e59f4727df0143a

canonical host note: huggingface.co resolves to an IPv6 address only on this machine
(`getent hosts huggingface.co` -> 2a03:2880:f12c:183:face:b00c:0:25de) and curl to it times out after 15s;
the card was read from the public mirror above, so treat it as secondary evidence.

```
> [!Tip]
> We recommend using the following set of sampling parameters for generation
> - Non-thinking mode for text tasks: `temperature=1.0, top_p=1.00, top_k=20, min_p=0.0, presence_penalty=2.0, repetition_penalty=1.0`
> - Non-thinking mode for VL tasks: `temperature=0.7, top_p=0.80, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0`
> - Thinking mode for text tasks: `temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0`
> - Thinking mode for VL or precise coding (e.g. WebDev) tasks : `temperature=0.6, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0, repetition_penalty=1.0`
> 
> Please note that the support for sampling parameters varies according to inference frameworks.

```
