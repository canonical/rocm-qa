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

# Basic build test
cat > main.c << END
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

int main() {
  enum { N = 5 };
  float hArr[N] = { 1, 2, 3, 4, 5 };
  float *dArr;
  CHECK_HIP(hipMalloc((void**)&dArr, sizeof(float) * N));
  CHECK_HIP(hipMemcpy((void**)dArr, hArr, sizeof(float) * N, hipMemcpyHostToDevice));
  CHECK_HIP(hipMemcpy((void**)hArr, dArr, sizeof(float) * N, hipMemcpyDeviceToHost));
  for (int i = 0; i < N; ++i) {
    printf("%f\n", hArr[i]);
  }
  CHECK_HIP(hipFree(dArr));
  return 0;
}
END
echo '$ cat main.c'
cat main.c
echo '$ gcc -D__HIP_PLATFORM_AMD__ main.c -lamdhip64 -o main'
gcc -D__HIP_PLATFORM_AMD__ main.c -lamdhip64 -o main

