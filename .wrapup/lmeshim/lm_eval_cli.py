#!/usr/bin/env python3
"""lm_eval launcher for the loglikelihood tasks against the local echo shim.

`llama-server` build 4399 no longer implements OpenAI `echo` (it rejects/ignores it),
so lm_eval's `--model gguf` cannot obtain prompt-token logprobs from it.  The
`.wrapup/lmeval_run.py` shim rebuilds them exactly.  The shim needs to know where the
context ends and the continuation begins; lm_eval's `GGUFLM.loglikelihood` has both
strings but only puts their concatenation on the wire, so this launcher patches
`GGUFLM.gguf_completion` to add them as `__context` / `__continuation`.

Everything else -- tasks, metrics, scoring, aggregation -- is stock lm_eval; the
command line keeps the standard `--model gguf` model type.
"""
from __future__ import annotations

import logging
import time

import requests
from requests.exceptions import RequestException

from lm_eval.models import gguf as _gguf

logger = logging.getLogger(__name__)


def gguf_completion(self, context, continuation=None, stop=None, retries=3, delay=5, **kwargs):
    for _ in range(retries):
        try:
            prompt = context
            request = {
                "prompt": prompt,
                "logprobs": self.logprobs,
                "temperature": self.temperature,
            }
            if continuation:
                prompt += continuation
                request.update({"prompt": prompt, "max_tokens": 1, "echo": True})
                # extra fields consumed by the shim; needed to locate the boundary
                request.update({"__context": context, "__continuation": continuation})
            if stop is not None:
                request["stop"] = stop
            response = requests.post(f"{self.base_url}/v1/completions", json=request)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"RequestException: {e}")
            time.sleep(delay)
    raise RuntimeError(f"Failed to get a valid response after {retries} retries.")


_gguf.GGUFLM.gguf_completion = gguf_completion

from lm_eval.__main__ import cli_evaluate  # noqa: E402

if __name__ == "__main__":
    cli_evaluate()
