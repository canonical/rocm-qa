#!/bin/bash
set -euo pipefail

# Smoke test to verify hipify-clang and hipify-perl are functional.
# This test validates:
#   1. hipify-clang transforms a CUDA API call to its HIP equivalent
#   2. hipify-perl translates a CUDA include to its HIP equivalent
#   3. (optional) hipify-clang handles CUDA kernel syntax when CUDA toolkit is present

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT
cd "$WORKDIR"

cat > sample_clang.cu <<'EOF'
// Minimal CUDA-like API sample for hipify-clang that avoids CUDA language features
// Uses a forward declaration so no CUDA headers are needed.
extern int cudaDeviceSynchronize();
int main() { return cudaDeviceSynchronize(); }
EOF

cat > sample_perl.cu <<'EOF'
// Minimal CUDA sample for hipify-perl that exercises include translation
#include <cuda_runtime.h>
int main() { return 0; }
EOF

echo "[TEST 1] Testing hipify-clang (API call)..."

/usr/bin/hipify-clang --hip-kernel-execution-syntax \
  --extra-arg-before=-nocudainc \
  -o sample_clang.hip.cu \
  sample_clang.cu

if [ ! -f sample_clang.hip.cu ]; then
  echo "[TEST 1] FAIL: hipify-clang did not produce output file" >&2
  exit 1
fi

if grep -q "hipDeviceSynchronize" sample_clang.hip.cu; then
  echo "[TEST 1] PASS: hipify-clang transformed API call as expected"
  head -n 200 sample_clang.hip.cu
else
  echo "[TEST 1] FAIL: hipify-clang did not transform API call" >&2
  head -n 200 sample_clang.hip.cu
  exit 1
fi

echo "[TEST 2] Testing hipify-perl..."
/usr/bin/hipify-perl sample_perl.cu > sample_perl.hip.cu

if [ ! -f sample_perl.hip.cu ]; then
  echo "[TEST 2] FAIL: hipify-perl did not produce output file" >&2
  exit 1
fi

if grep -q "hip_runtime.h" sample_perl.hip.cu; then
  echo "[TEST 2] PASS: hipify-perl translated include as expected"
  head -n 200 sample_perl.hip.cu
else
  echo "[TEST 2] FAIL: hipify-perl did not translate include to hip_runtime.h" >&2
  head -n 200 sample_perl.hip.cu
  exit 1
fi

echo "[TEST 3] Probing CUDA installation for optional CUDA syntax test..."
CUDA_PATH=""
CUDA_INCLUDE=""

NVCC_BIN=$(command -v nvcc 2>/dev/null || true)
NVCC_PREFIX=""
if [ -n "$NVCC_BIN" ]; then
  NVCC_DIR=$(dirname "$NVCC_BIN")
  NVCC_PREFIX=$(dirname "$NVCC_DIR")
fi
for cand in /usr/lib/cuda /usr/local/cuda "$NVCC_PREFIX"; do
  [ -z "$cand" ] && continue
  if [ -d "$cand/nvvm" ] && { [ -d "$cand/nvvm/libdevice" ] || [ -e "$cand/nvvm/libdevice" ]; }; then
    CUDA_PATH="$cand"
    break
  fi
done

if [ -n "$CUDA_PATH" ] && [ -d "$CUDA_PATH/include" ]; then
  CUDA_INCLUDE="$CUDA_PATH/include"
elif [ -f /usr/include/cuda_runtime.h ]; then
  CUDA_INCLUDE=/usr/include
fi

if [ -n "$CUDA_PATH" ] && [ -n "$CUDA_INCLUDE" ]; then
  echo "[TEST 3] Found CUDA_PATH=$CUDA_PATH, CUDA_INCLUDE=$CUDA_INCLUDE"
  cat > sample_cuda_syntax.cu <<'EOF'
#include <cuda_runtime.h>
__global__ void kernel() {}
int main() { kernel<<<1,1>>>(); return 0; }
EOF

  /usr/bin/hipify-clang --hip-kernel-execution-syntax \
    --cuda-path="$CUDA_PATH" --extra-arg-before=-x --extra-arg-before=cuda -I"$CUDA_INCLUDE" \
    -o sample_cuda_syntax.hip.cu sample_cuda_syntax.cu

  if [ ! -f sample_cuda_syntax.hip.cu ]; then
    echo "[TEST 3] FAIL: hipify-clang (CUDA syntax) did not produce output file" >&2
    exit 1
  fi

  if grep -q "hipLaunchKernelGGL" sample_cuda_syntax.hip.cu; then
    echo "[TEST 3] PASS: hipify-clang transformed kernel launch syntax as expected"
    head -n 200 sample_cuda_syntax.hip.cu
  else
    echo "[TEST 3] FAIL: hipify-clang did not transform kernel launch syntax" >&2
    head -n 200 sample_cuda_syntax.hip.cu
    exit 1
  fi
else
  echo "[TEST 3] SKIP: CUDA toolkit layout not detected"
fi

echo "hipify smoke test: PASS"
