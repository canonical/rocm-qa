#include <rocsparse/rocsparse.h>
#include <hip/hip_runtime.h>
#include <iostream>
#include <vector>
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
    using rint = rocsparse_int;
    rint n = 4096;

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> dist(-1.0, 1.0);

    auto myrand = [&]() -> float {return dist(gen);};

    std::vector<float> xin(n);
    std::generate(xin.begin(), xin.end(), myrand);

    rocsparse_handle handle;
    rocsparse_create_handle(&handle); 

    std::vector<rint> row_ptr(n + 1);
    std::vector<rint> col(3 * n);
    std::vector<float> data(3 * n);
    
    //Second order finite differences matrix in 1D
    row_ptr[0] = 0;
    for(size_t i = 0; i < n; i++){
        rint off = row_ptr[i];
        if(i > 0){
            col[off] = i - 1;
            data[off++] = -1.0f;
        }
        col[off] = i;
        data[off++] = 2.0f;
        if(i < n - 1){
            col[off] = i + 1;
            data[off++] = -1.0f;
        }
        row_ptr[i + 1] = off;
    }

    rint *rp;
    rint *c;
    float *d;

    float *x;
    float *y;
    HIP_CHECK(hipMalloc((void **)&rp, sizeof *rp * (n + 1)));
    HIP_CHECK(hipMalloc((void **)&c, sizeof *c * 3 * n));
    HIP_CHECK(hipMalloc((void **)&d, sizeof *d * 3 * n));

    HIP_CHECK(hipMalloc((void **)&x, sizeof *x * n));
    HIP_CHECK(hipMalloc((void **)&y, sizeof *y * n));

    HIP_CHECK(hipMemcpy(rp, row_ptr.data(), sizeof *rp * (n + 1), hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(c, col.data(), sizeof *c * 3 * n, hipMemcpyHostToDevice));
    HIP_CHECK(hipMemcpy(d, data.data(), sizeof *d * 3 * n, hipMemcpyHostToDevice));

    HIP_CHECK(hipMemcpy(x, xin.data(), sizeof *x * n, hipMemcpyHostToDevice));

    float alpha = 14.124f;
    float beta = 0.0f;

    rocsparse_mat_descr descr;
    rocsparse_create_mat_descr(&descr);

    rocsparse_scsrmv(handle, rocsparse_operation_none,
        n, n, 3 * n - 2, &alpha, descr, d, rp, c, nullptr,
        x, &beta, y);

    std::vector<float> yout(n);
    HIP_CHECK(hipMemcpy(yout.data(), y, sizeof *y * n, hipMemcpyDeviceToHost));

    float tol = 0.0001f;
    for(rint i = 0; i < n; i++){
        for(rint jj = row_ptr[i]; jj < row_ptr[i + 1]; jj++){
            rint j = col[jj];
            yout[i] -= alpha * data[jj] * xin[j];
        }
        if(std::abs(yout[i]) > tol){
            std::cout << "Entry " << i << " is not computed correctly.\n";
            std::cout << "Expected 0 but got " <<  yout[i] << std::endl;
            return 1;
        }
    }

    std::cout << "TESTS PASSED!" << std::endl;

    rocsparse_destroy_handle(handle);
    rocsparse_destroy_mat_descr(descr);
    HIP_CHECK(hipFree(rp));
    HIP_CHECK(hipFree(c));
    HIP_CHECK(hipFree(d));
    HIP_CHECK(hipFree(x));
    HIP_CHECK(hipFree(y));
}
