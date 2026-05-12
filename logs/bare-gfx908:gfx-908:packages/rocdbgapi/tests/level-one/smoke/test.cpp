#include <cstdlib>
#include <cstring>
#include <iostream>
#include <amd-dbgapi/amd-dbgapi.h>

int main() {
    int ret = 0;

    // 1. Query the installed library version
    uint32_t major = 0, minor = 0, patch = 0;
    amd_dbgapi_get_version(&major, &minor, &patch);

    std::cout << "ROCm Debugger API Version: "
              << major << "." << minor << "." << patch << std::endl;

    // Verify the runtime version matches what the header declares
    if (major != AMD_DBGAPI_VERSION_MAJOR || minor != AMD_DBGAPI_VERSION_MINOR) {
        std::cerr << "FAIL: version mismatch - header says "
                  << AMD_DBGAPI_VERSION_MAJOR << "." << AMD_DBGAPI_VERSION_MINOR
                  << " but library reports "
                  << major << "." << minor << std::endl;
        ret = 1;
    }

    // 2. Query the build name string
    const char* build_name = amd_dbgapi_get_build_name();
    if (build_name && std::strlen(build_name) > 0) {
        std::cout << "Build string: " << build_name << std::endl;
    } else {
        std::cerr << "FAIL: amd_dbgapi_get_build_name returned null or empty"
                  << std::endl;
        ret = 1;
    }

    // 3. Exercise amd_dbgapi_get_status_string (works without initialization)
    const char* status_str = nullptr;
    amd_dbgapi_status_t status =
        amd_dbgapi_get_status_string(AMD_DBGAPI_STATUS_SUCCESS, &status_str);
    if (status != AMD_DBGAPI_STATUS_SUCCESS || !status_str) {
        std::cerr << "FAIL: amd_dbgapi_get_status_string failed" << std::endl;
        ret = 1;
    } else {
        std::cout << "Status string for SUCCESS: " << status_str << std::endl;
    }

    if (ret == 0)
        std::cout << "rocdbgapi smoke test: PASS" << std::endl;
    else
        std::cout << "rocdbgapi smoke test: FAIL" << std::endl;

    return ret;
}
