#!/usr/bin/env python3
"""Entry program for news-image-20261120 (agent 4, plucky-harbor-48).

Copies the pre-rendered entry.png — drawn by render.py and committed in
this repository — to $MAKEFUN_OUTPUT_DIR/entry.png.

Stdlib only, no network, deterministic: a byte-for-byte copy, so two runs
produce identical output.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    src = os.path.join(HERE, "entry.png")
    dst = os.path.join(out_dir, "entry.png")
    os.makedirs(out_dir, exist_ok=True)
    shutil.copyfile(src, dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
