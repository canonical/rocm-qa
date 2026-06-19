#include <hipblaslt/hipblaslt.h>
#include <stdio.h>
#include <stdlib.h>

#define CHECK(call)                                                  \
    do                                                               \
    {                                                                \
        hipblasStatus_t _s = (call);                                 \
        if(_s != HIPBLAS_STATUS_SUCCESS)                             \
        {                                                            \
            fprintf(stderr, "FAILED: %s returned %d\n", #call, (int)_s); \
            return EXIT_FAILURE;                                     \
        }                                                            \
    } while(0)

int main(void)
{
    hipblasLtHandle_t handle;
    CHECK(hipblasLtCreate(&handle));

    int version = 0;
    CHECK(hipblasLtGetVersion(handle, &version));
    printf("hipBLASLt version: %d.%d.%d\n",
           version / 100000,
           (version / 100) % 1000,
           version % 100);

    char* arch = NULL;
    CHECK(hipblasLtGetArchName(&arch));
    printf("GPU architecture: %s\n", arch ? arch : "(unknown)");

    CHECK(hipblasLtDestroy(handle));

    printf("TESTS PASSED!\n");
    return EXIT_SUCCESS;
}
