#!/usr/bin/env python3

import ctypes
import sys

import torch


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not torch.distributed.is_nccl_available():
        fail("PyTorch NCCL backend is not available")

    try:
        lib = ctypes.CDLL("librccl.so.1", mode=ctypes.RTLD_GLOBAL)
    except OSError as e:
        fail(f"Failed to load librccl.so.1: {e}")

    print("PASS: PyTorch NCCL backend available")
    print(f"Loaded library: {lib._name}")


if __name__ == "__main__":
    main()
