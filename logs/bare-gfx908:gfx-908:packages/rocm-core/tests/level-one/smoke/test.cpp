#include <cstdint>
#include <cstdio>
#include <cinttypes>
#include <cstdlib>

// Disable warning about relying on rocm core version
#define NO_ROCMCORE_VERSION_WARNING

#include <rocm-core/rocm_getpath.h>
#include <rocm-core/rocm_version.h>

int check_rocm_core_path()
{
    char *installPath=NULL;
    unsigned int installPathLen = 0;
    PathErrors_t installStatus;

    installStatus = getROCmInstallPath( &installPath, &installPathLen );

    if(installStatus !=PathSuccess )
    {  // error occured
        free(installPath); //caller must free allocated memory after usage.
        std::printf("ERROR: recieved return code from getROCmInstallPath: %d\n", installStatus);
        return 255;
    }

    std::printf("SUCCESS: ROCm install path from rocm-core detected as: %s\n", installPath);
    free(installPath); //caller must free allocated memory after usage.
    return 0;

}

int check_rocm_version()
{
    unsigned int major=0,minor=0,patch=0,ret=0;

    ret = getROCmVersion(&major,&minor,&patch);

    if(ret !=VerSuccess )
    {
        std::printf("ERROR: recieved return code from getROCMVersion: %d\n", ret);
        return 255;
    }

    else
    {
        std::printf("SUCCESS: ROCm Version from rocm-core detected as: %d.%d.%d\n", major, minor, patch);
        return 0;
    }

}

int main()
{
    int path_ret = check_rocm_core_path();
    int version_ret = check_rocm_version();

    if(path_ret != 0 || version_ret != 0)
    {
        std::printf("One or more tests failed. Please check the logs for more details.\n");
        return 255;
    }

    std::printf("All tests passed successfully.\n");
    return 0;
}
