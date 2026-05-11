#include <hsa/hsa.h>

#include <cstdlib>
#include <iostream>

#define HSA_CHECK(cmd) \
    do { \
        hsa_status_t s = cmd; \
        if (s != HSA_STATUS_SUCCESS) { \
            const char *msg = nullptr; \
            hsa_status_string(s, &msg); \
            std::cerr << "HSA error: " << (msg ? msg : "unknown") \
                      << " at " << __FILE__ << ":" << __LINE__ << std::endl; \
            std::exit(EXIT_FAILURE); \
        } \
    } while (0)

static hsa_status_t count_agents(hsa_agent_t agent, void *data)
{
    auto *counts = static_cast<int (*)[2]>(data);
    hsa_device_type_t type;
    HSA_CHECK(hsa_agent_get_info(agent, HSA_AGENT_INFO_DEVICE, &type));
    if (type == HSA_DEVICE_TYPE_CPU) {
        ++(*counts)[0];
    } else if (type == HSA_DEVICE_TYPE_GPU) {
        ++(*counts)[1];
    }
    return HSA_STATUS_SUCCESS;
}

int main()
{
    HSA_CHECK(hsa_init());

    uint16_t major = 0, minor = 0;
    HSA_CHECK(hsa_system_get_info(HSA_SYSTEM_INFO_VERSION_MAJOR, &major));
    HSA_CHECK(hsa_system_get_info(HSA_SYSTEM_INFO_VERSION_MINOR, &minor));
    std::cout << "HSA runtime version: " << major << "." << minor << std::endl;

    int counts[2] = {0, 0};
    HSA_CHECK(hsa_iterate_agents(count_agents, &counts));
    std::cout << "CPU agents: " << counts[0] << ", GPU agents: " << counts[1] << std::endl;

    if (counts[0] + counts[1] == 0) {
        std::cerr << "No HSA agents found" << std::endl;
        HSA_CHECK(hsa_shut_down());
        return 1;
    }

    HSA_CHECK(hsa_shut_down());
    std::cout << "TESTS PASSED!" << std::endl;
    return 0;
}
