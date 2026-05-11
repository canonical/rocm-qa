#include <hipblas-common.h>
#include <cassert>

int main() {
    hipblasStatus_t status = HIPBLAS_STATUS_SUCCESS;
    assert(status == 0);

    hipblasOperation_t op = HIPBLAS_OP_T;
    assert(op == 112);

    hipblasComputeType_t compute = HIPBLAS_COMPUTE_32F;
    assert(compute == 2);

#if __cplusplus >= 201103L
    static_assert(HIPBLAS_OP_N == 111, "HIPBLAS_OP_N value mismatch");
    static_assert(HIPBLAS_OP_T == 112, "HIPBLAS_OP_T value mismatch");
    static_assert(HIPBLAS_OP_C == 113, "HIPBLAS_OP_C value mismatch");
#endif

    return 0;
}
