#include <hipsolver/hipsolver.h>
#include <hip/hip_runtime.h>
#include <vector>
#include <random>
#include <algorithm>
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

int main()
{
    size_t n = 64;
    size_t m = 41;
    size_t size = n * m;

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> dist(-1.0, 1.0);
    auto myrand = [&](){return dist(gen);};

    float *a;
    HIP_CHECK(hipMalloc((void**)&a, sizeof *a * size));

    std::vector<float> ain(size);
    std::generate(ain.begin(), ain.end(), myrand);

    HIP_CHECK(hipMemcpy(a, ain.data(), sizeof *a * size, hipMemcpyHostToDevice));

    hipsolverHandle_t handle;
    hipsolverCreate(&handle);

    float *work;
    int size_work;
    hipsolverSgesvd_bufferSize(handle, 'N', 'N', n, m, &size_work);
    HIP_CHECK(hipMalloc((void**)&work, size_work));

    size_t dim = std::min(n, m);
    float *s;
    float *rwork;
    HIP_CHECK(hipMalloc((void**)&s, sizeof *s * dim));
    HIP_CHECK(hipMalloc((void**)&rwork, sizeof *rwork * dim));

    int *devInfo;
    HIP_CHECK(hipMalloc((void**)&devInfo, sizeof *devInfo));
    hipsolverSgesvd(handle, 'N', 'N', n, m, a, n,
        s, NULL, n, NULL, n, work, size_work, rwork, devInfo);

    std::vector<float> sout(dim);
    HIP_CHECK(hipMemcpy(sout.data(), s, sizeof *s * dim, hipMemcpyDeviceToHost));

    float tol = 0.001f;
    for(size_t i = 0; i < dim; i++){
        if(sout[i] / sout[0] < tol){
            std::cout << "Rank of matrix is " << i + 1
                << " but should have rank " << dim << std::endl;
            return 1;
        }
    }

    std::cout << "TESTS PASSED!" << std::endl;

    HIP_CHECK(hipFree(a));
    HIP_CHECK(hipFree(s));
    HIP_CHECK(hipFree(rwork));
    HIP_CHECK(hipFree(work));
    HIP_CHECK(hipFree(devInfo));
    hipsolverDestroy(handle);
}
