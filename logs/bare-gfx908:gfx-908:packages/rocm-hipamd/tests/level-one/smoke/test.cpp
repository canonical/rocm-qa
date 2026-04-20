#include <iostream>
#include <cmath>
#include <vector>
#include <hip/hip_runtime.h>

#define HIP_CHECK(call)                                      \
    do {                                                     \
        hipError_t err = call;                               \
        if (err != hipSuccess) {                             \
            std::cerr << "HIP error: "                       \
                      << hipGetErrorString(err)              \
                      << " at " << __FILE__ << ":"           \
                      << __LINE__ << std::endl;              \
            exit(1);                                         \
        }                                                    \
    } while (0)

__global__
void saxpy(int n, float a, const float *x, float *y)
{
    int i = hipThreadIdx_x + hipBlockDim_x * hipBlockIdx_x;
    if(i < n){
        y[i] = a * x[i] + y[i];
    }
}

__global__
void sset(int n, float a, float *x)
{
    int i = hipThreadIdx_x + hipBlockDim_x * hipBlockIdx_x;
    if(i < n){
        x[i] = a;
    }
}

int main()
{
    hipDeviceProp_t prop;
    HIP_CHECK(hipGetDeviceProperties(&prop, 0));

    std::cout << "Agent " << prop.name << "\n";
    std::cout << "System version " << prop.major
              << "." << prop.minor << "\n";

    int n = 1024;
    float *x;
    float *y;

    HIP_CHECK(hipMalloc((void**)&x, sizeof *x * n));
    HIP_CHECK(hipMalloc((void**)&y, sizeof *y * n));

    std::vector<float> xin(n);
    for(int i = 0; i < n; i++){
        xin[i] = -1.0f + 2.0f * i / n;
    }

    HIP_CHECK(hipMemcpy(x, xin.data(), sizeof *x * n, hipMemcpyHostToDevice));

    float ac = -14.412f;
    hipLaunchKernelGGL(sset, dim3(1), dim3(n), 0, 0, n, ac, y);
    HIP_CHECK(hipGetLastError());
    HIP_CHECK(hipDeviceSynchronize());

    float a = 5321.124f;
    hipLaunchKernelGGL(saxpy, dim3(1), dim3(n), 0, 0, n, a, x, y);
    HIP_CHECK(hipGetLastError());
    HIP_CHECK(hipDeviceSynchronize());

    std::vector<float> yout(n);
    HIP_CHECK(hipMemcpy(yout.data(), y, sizeof *y * n, hipMemcpyDeviceToHost));

    HIP_CHECK(hipFree(x));
    HIP_CHECK(hipFree(y));

    for(int i = 0; i < n; i++){
        float expected = ac;
        float computed = yout[i] - a * xin[i];

        if(std::abs(computed - expected) > 0.001f){
            std::cout << "Test failed at index " << i
                      << " with entry " << computed
                      << " (" << expected << ")\n";
            return 1;
        }
    }

    std::cout << "TESTS PASSED!" << std::endl;
}
