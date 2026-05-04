#! /bin/sh
set -e

if [ "${AUTOPKGTEST_TMP}" = "" ]
then
	AUTOPKGTEST_TMP=$(mktemp -d /tmp/${pkg}-test.XXXXXX)
	# Double quote below to expand the temporary directory variable now
	# versus later is on purpose.
	# shellcheck disable=SC2064
	trap "rm -rf ${AUTOPKGTEST_TMP}" 0 INT QUIT ABRT PIPE TERM
fi
cd "$AUTOPKGTEST_TMP"

# Superficial tests
echo '$ hipcc --help'
hipcc --help
echo '$ hipcc --version'
hipcc --version

# Basic build test
cat > main.hip << END
#include <stdio.h>
#include <stdlib.h>
#include <hip/hip_runtime.h>

#define CHECK_HIP(expr) do {              \
  hipError_t result = (expr);             \
  if (result != hipSuccess) {             \
    fprintf(stderr, "%s:%d: %s (%d)\n",   \
      __FILE__, __LINE__,                 \
      hipGetErrorString(result), result); \
    exit(EXIT_FAILURE);                   \
  }                                       \
} while(0)

__global__ void sq_arr(float *arr, int n) {
  int tid = blockDim.x*blockIdx.x + threadIdx.x;
  if (tid < n) {
    arr[tid] = arr[tid] * arr[tid];
  }
}

int main() {
  enum { N = 5 };
  float hArr[N] = { 1, 2, 3, 4, 5 };
  float *dArr;
  CHECK_HIP(hipMalloc(&dArr, sizeof(float) * N));
  CHECK_HIP(hipMemcpy(dArr, hArr, sizeof(float) * N, hipMemcpyHostToDevice));
  sq_arr<<<dim3(1), dim3(32,1,1), 0, 0>>>(dArr, N);
  CHECK_HIP(hipMemcpy(hArr, dArr, sizeof(float) * N, hipMemcpyDeviceToHost));
  for (int i = 0; i < N; ++i) {
    printf("%f\n", hArr[i]);
  }
  CHECK_HIP(hipFree(dArr));
  return 0;
}
END
echo '$ cat main.hip'
cat main.hip
echo '$ hipcc main.hip --offload-arch=gfx900 -o main'
hipcc main.hip --offload-arch=gfx900 -o main

