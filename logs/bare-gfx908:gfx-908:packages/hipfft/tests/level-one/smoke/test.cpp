#include <hipfft/hipfft.h>
#include <hip/hip_runtime.h>
#include <vector>
#include <numeric>
#include <cmath>
#include <iostream>

#define HIP_CHECK(cmd) \
    do { \
        hipError_t e = cmd; \
        if (e != hipSuccess) { \
            std::cerr << "HIP error: " << hipGetErrorString(e) \
                      << " at " << __FILE__ << ":" << __LINE__ << std::endl; \
            std::exit(EXIT_FAILURE); \
        } \
    } while (0)

#define HIPFFT_CHECK(cmd) \
    do { \
        hipfftResult e = cmd; \
        if (e != HIPFFT_SUCCESS) { \
            std::cerr << "HIPFFT error: " << e \
                      << " at " << __FILE__ << ":" << __LINE__ << std::endl; \
            std::exit(EXIT_FAILURE); \
        } \
    } while (0)

int main()
{
    size_t size = 1024 * 1024;

    hipfftComplex *x;
    HIP_CHECK(hipMalloc((void**)&x, sizeof *x * size));

    std::vector<hipfftComplex> xin(size);
    for(auto &xx: xin){
        xx.x = 1.0f;
        xx.y = 0.0f;
    }
    HIP_CHECK(hipMemcpy(x, xin.data(), sizeof *x * size, hipMemcpyHostToDevice));

    hipfftHandle plan;
    HIPFFT_CHECK(hipfftPlan1d(&plan, size, HIPFFT_C2C, 1));

    HIPFFT_CHECK(hipfftExecC2C(plan, x, x, HIPFFT_FORWARD));

    std::vector<hipfftComplex> xout(size);
    HIP_CHECK(hipMemcpy(xout.data(), x, sizeof *x * size, hipMemcpyDeviceToHost));

    std::vector<hipfftComplex> xref(size);
    for(auto &xx: xref){
        xx.x = 0.0f;
        xx.y = 0.0f;
    }
    xref[0].x = 1.0f * size;
    
    float tol = 0.001f;
    for(size_t i = 0; i < size; i++){
        if(std::abs(xref[i].x - xout[i].x) + std::abs(xref[i].y - xout[i].y) > tol){
            std::cout << "Element mismatch at index " << i << "\n";
            std::cout << "Expected: " << xref[i].x << " " << xref[i].y << "\n";
            std::cout << "Actual  : " << xout[i].x << " " << xout[i].y << "\n";
            return 1;
        }
    }

    std::cout << "TESTS PASSED!" << std::endl;

    HIP_CHECK(hipFree(x));
    HIPFFT_CHECK(hipfftDestroy(plan));
}
