#include <hipcub/hipcub.hpp>
#include <vector>
#include <iostream>
#include <random>
#include <algorithm>

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
    size_t size = 1024;
    std::vector<float> xin(size);

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> dist(-1.0, 1.0);

    auto myrand = [&]() -> float {return dist(gen);};

    std::generate(xin.begin(), xin.end(), myrand);

    float *x;
    float *xs;
    HIP_CHECK(hipMalloc((void**)&x, sizeof *x * size));
    HIP_CHECK(hipMalloc((void**)&xs, sizeof *xs * size));

    HIP_CHECK(hipMemcpy(x, xin.data(), sizeof *x * size, hipMemcpyHostToDevice));

    void *tmp_storage = nullptr;
    size_t tmp_storage_bytes = 0;
    hipcub::DeviceRadixSort::SortKeys(tmp_storage, tmp_storage_bytes, x, xs, size);
    HIP_CHECK(hipMalloc((void**)&tmp_storage, tmp_storage_bytes));
    hipcub::DeviceRadixSort::SortKeys(tmp_storage, tmp_storage_bytes, x, xs, size);

    std::vector<float> xout(size);
    HIP_CHECK(hipMemcpy(xout.data(), xs, sizeof *xs * size, hipMemcpyDeviceToHost));

    for(size_t i = 1; i < size; i++){
        if(xout[i - 1] > xout[i]){
            std::cout << "Elements not sorted at index " << i << "\n";
            std::cout << x[i - 1] << " " << x[i] << std::endl;
            return 1;
        }
    }
    std::cout << "TESTS PASSED!" << std::endl;

    HIP_CHECK(hipFree(x));
    HIP_CHECK(hipFree(xs));
    HIP_CHECK(hipFree(tmp_storage));
}
