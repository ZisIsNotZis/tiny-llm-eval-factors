#!/usr/bin/env python3
"""Unit checks for `mpl_run.strip_fences` (the MultiPL-E scoring postprocess, method.m48).

m48 fixes four behaviours, and each one has a way to be wrong that a passing
cell count would hide:

1. an *unterminated* line-leading fence is stripped — the dataset stop token
   (`\n}`) usually cuts the completion before the closing fence, so the common
   case is the unterminated one;
2. a *terminated* fence is stripped together with its closing line;
3. a completion with no fence keeps its indentation byte-for-byte — a Python
   completion is a function body, so de-indenting it is an IndentationError;
4. a fence that is not at the start of the completion is left untouched.

Case 5 pins the tolerance m48 relies on: the fence may be preceded by blank
lines, and those are removed with it.

Run: python3 .wrapup/test_mpl_postprocess.py   (exit 0 = every case passed)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mpl_run import strip_fences  # noqa: E402  (path set above)


def unterminated_fence_stripped():
    got = strip_fences("```python\ndef f():\n    return 1")
    assert got == "def f():\n    return 1", repr(got)


def terminated_fence_stripped():
    got = strip_fences("```python\ndef f():\n    return 1\n```\n")
    assert got == "def f():\n    return 1", repr(got)


def no_fence_keeps_indentation():
    body = "    return 1\n    x = 2\n    return x"
    got = strip_fences(body)
    assert got == body, repr(got)


def fence_not_at_start_untouched():
    body = "def f():\n    ```python\n    return 1"
    got = strip_fences(body)
    assert got == body, repr(got)


def leading_blank_line_before_fence_stripped():
    got = strip_fences("\n```python\ndef f():\n    return 1")
    assert got == "def f():\n    return 1", repr(got)


CASES = [
    ("unterminated fence stripped", unterminated_fence_stripped),
    ("terminated fence stripped", terminated_fence_stripped),
    ("no fence keeps python indentation byte-identical", no_fence_keeps_indentation),
    ("fence not at start left untouched", fence_not_at_start_untouched),
    ("leading blank line before fence stripped", leading_blank_line_before_fence_stripped),
]


def main():
    failed = 0
    for name, fn in CASES:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
        else:
            print(f"PASS {name}")
    print(f"{len(CASES) - failed}/{len(CASES)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
