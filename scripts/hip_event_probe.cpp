// Standalone ROCm HIP diagnostic: not a certified GPU billing meter.
#include <hip/hip_runtime.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>

__global__ void workload(float* out) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    float x = i * 0.001f + 1.0f;
    for (int j = 0; j < 4096; ++j) x = x * 1.000001f + 0.000001f;
    out[i] = x;
}

#define HIP_CHECK(call) do { \
    hipError_t err = (call); \
    if (err != hipSuccess) { \
        std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(err)); \
        return 2; \
    } \
} while (0)

int main() {
    float* data = nullptr;
    hipEvent_t start = nullptr, stop = nullptr;
    HIP_CHECK(hipSetDevice(0));
    HIP_CHECK(hipMalloc(&data, 65536 * sizeof(float)));
    HIP_CHECK(hipEventCreate(&start));
    HIP_CHECK(hipEventCreate(&stop));
    auto begun = std::chrono::steady_clock::now();
    double measured_ms = 0;
    unsigned long count = 0;
    for (; std::chrono::duration<double>(std::chrono::steady_clock::now() - begun).count() < 10.0; ++count) {
        HIP_CHECK(hipEventRecord(start));
        hipLaunchKernelGGL(workload, dim3(256), dim3(256), 0, 0, data);
        HIP_CHECK(hipGetLastError());
        HIP_CHECK(hipEventRecord(stop));
        HIP_CHECK(hipEventSynchronize(stop));
        float ms = 0;
        HIP_CHECK(hipEventElapsedTime(&ms, start, stop));
        measured_ms += ms;
    }
    HIP_CHECK(hipEventDestroy(stop));
    HIP_CHECK(hipEventDestroy(start));
    HIP_CHECK(hipFree(data));
    std::printf("GPU event elapsed: %.3f seconds\nIterations: %lu\n", measured_ms / 1000.0, count);
    std::puts("Diagnostic only: do not bill HIP event elapsed as exclusive GPU time");
    return 0;
}
