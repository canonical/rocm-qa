---
layout: default
title: Documentation
---

# Documentation

## Overview

This site displays test results for ROCm packages on Ubuntu and is automatically updated after each test run.

## How to access the packages?

Packages listed [here](/rocm-qa) can be accessed via apt directly, since Ubuntu 26.04. If you would like to access
the development version of these packages, please see the instructions in [this section](#development-ppa).

## Test Results

The [main page](/rocm-qa) shows the latest test results from automated test runs.

### How to interpret the tables?

Test results tables consists of "Test Suite", "System" and "Result" columns.

{: .spacing-sm }

#### **Test Suite**: Name of the test suite we run using the package.

_autopkgtest_: Simply runs autopkgtests defined for the debian package. In addition to the usual "FAIL" status of autopkgtest,
if a package doesn't have any autopkgtest, then the result will be marked as "FAIL" as well.

_level-one_: Placeholder name for a test suite that will run basic heartbeat tests with a set of applications (details to be added).

{: .spacing-sm }

#### System: Name of the system the test ran on.

#### Result: Result of the test run either FAIL or PASS.

## Development PPA

ROCm packaging team in Canonical maintains the development of ROCm packages under the name of [\~bullwinkle-team](https://launchpad.net/~bullwinkle-team) in [Launchpad](https://launchpad.net).

If the packages already available in the Ubuntu archive are not enough for you and you want to use packages that are still in the development stage,
you can use the following instructions to enable the PPA in your system and install the specific package you want from the PPA.

{: .spacing-sm }

```
sudo add-apt-repository ppa:bullwinkle-team/rocm-devel-21

# Install all rocm packages
sudo apt install rocm-dev
# Or only install what you need
sudo apt install hipcc
```

{: .spacing-sm }
See the development PPAs below:

- [ppa:rocm-devel-21](https://launchpad.net/~bullwinkle-team/+archive/ubuntu/rocm-devel-21) : ROCm development archive which holds packages built against upstream [LLVM-21](https://launchpad.net/ubuntu/+source/llvm-toolchain-21)

## Badges

Dynamic badges are available for each package at:
`/badges/<package-name>.json`

These badges follow the [Shields.io endpoint schema](https://shields.io/endpoint) and can be used in README files or other documentation.
{: .spacing-md }
