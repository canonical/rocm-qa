#include <string>

#include <rocwmma/rocwmma-version.hpp>

#include <cstdio>
#include <cstdlib>

int main(void)
{
    std::string version = rocwmma_get_version();
    printf("rocWMMA version: %s\n", version.c_str());

    if(version.empty())
    {
        fprintf(stderr, "FAILED: rocwmma_get_version() returned an empty string\n");
        return EXIT_FAILURE;
    }

    std::string expected = std::to_string(ROCWMMA_VERSION_MAJOR) + "."
                           + std::to_string(ROCWMMA_VERSION_MINOR) + "."
                           + std::to_string(ROCWMMA_VERSION_PATCH);

    if(version != expected)
    {
        fprintf(stderr,
                "FAILED: version mismatch: got '%s', expected '%s'\n",
                version.c_str(),
                expected.c_str());
        return EXIT_FAILURE;
    }

    printf("TESTS PASSED!\n");
    return EXIT_SUCCESS;
}
