-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA512

Format: 3.0 (quilt)
Source: rocm-llvm
Binary: hipcc, rocm-device-libs-21, libamd-comgr3, libamd-comgr-dev
Architecture: amd64 arm64 ppc64el
Version: 7.1.1+dfsg-0ubuntu1
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Uploaders: Xuanteng Huang <xuanteng.huang@outlook.com>, Christian Kastner <ckk@debian.org>, Cordell Bloor <cgmb@debian.org>
Homepage: https://github.com/ROCm/llvm-project
Standards-Version: 4.7.2
Vcs-Browser: https://salsa.debian.org/rocm-team/rocm-llvm
Vcs-Git: https://salsa.debian.org/rocm-team/rocm-llvm.git
Testsuite: autopkgtest
Testsuite-Triggers: cmake, g++, gcc, libamdhip64-dev, make, rocminfo
Build-Depends: debhelper-compat (= 13), cmake, clang-21, clang-tools-21, libclang-21-dev, libclang-rt-21-dev, libhsa-runtime-dev (>= 7.1.0~), libnuma-dev, lld-21, liblld-21-dev, llvm-21-dev, libzstd-dev, zlib1g-dev, libxml2-dev, chrpath
Package-List:
 hipcc deb devel optional arch=amd64,arm64,ppc64el
 libamd-comgr-dev deb libdevel optional arch=amd64,arm64,ppc64el
 libamd-comgr3 deb libs optional arch=amd64,arm64,ppc64el
 rocm-device-libs-21 deb libs optional arch=amd64,arm64,ppc64el
Checksums-Sha1:
 04050dcb150a35be90659b0f554b99f9abb65e5c 326252 rocm-llvm_7.1.1+dfsg.orig.tar.xz
 b552535b8cc4977aa06e25e4a2b099ebd188c3b4 14744 rocm-llvm_7.1.1+dfsg-0ubuntu1.debian.tar.xz
Checksums-Sha256:
 5546e11223730fbba1147f5ceb06a1608d0871ecfce201cd76d5dfcfbf9e521d 326252 rocm-llvm_7.1.1+dfsg.orig.tar.xz
 ee33c0b5733586d47a69e61032cdf31e82a28407bb49e7f05800f3fb4c140025 14744 rocm-llvm_7.1.1+dfsg-0ubuntu1.debian.tar.xz
Files:
 4d80c7ef947c5022a03c54c37ae0e777 326252 rocm-llvm_7.1.1+dfsg.orig.tar.xz
 533fb804c14f0dd71ebacb2376214ed1 14744 rocm-llvm_7.1.1+dfsg-0ubuntu1.debian.tar.xz
Original-Maintainer: Debian ROCm Team <debian-ai@lists.debian.org>

-----BEGIN PGP SIGNATURE-----

iQJUBAEBCgA+FiEEHhMS30txWLbr+d54JXQ4eWL+sNEFAmnfjKAgHHRhbGhhLmNh
bi5oYXZhZGFyQGNhbm9uaWNhbC5jb20ACgkQJXQ4eWL+sNEfNg/+JMs1DXe8gq3a
qLNV1mNsvQZxTQLz+ibtJsK0T73rkGTQLO/BBC8Gm2zhVqkYIaNKeMkIxdPcvrhu
TcD5V6R0nwkTThNGZSn5c6hdnVJWwmDwm4o0G6MLki3LOVm3kFc/3ZSsmrsiWog/
kQsOOB3q8zwQn8vgVpps3jVHJYTUMrkhIE1kupsLjLt5/AQ5Zg1BXjMNlUaar4sR
hKAN9sp1Ge+Rw2jCDjxutTFLzXszppbMhVYnnZdRX0I/7bjAOKICobkIhhjyV3qu
oe6i+aMI5ZZHYdW0mIayy2iL0Ok6aG71lsdO+jvY4TjsuhYQ0BOXCdZbbPDhAHIr
DISbMVpxf3QT1o3j+jYvJBTrQYz8dT9e10cK9UpbG61cJE4v63EcGa4WgZQYt9Vw
1pDIwvMXhtjBZ8rq8coYmuphkV+OFN7+Yeyre/BjTtffQXr/uHLswj4g/HcHDete
P3ohrioITu03ffz+N78tB/+Sn9f6J7fKxBypa4S7JZVNu84ZoKVN8xeOPawo07xq
zwXcOlqIVG/y2UpXufH+/xa/hvFHVd9xyZCTSW/P0gRrk06o8txG9HAT3kClNkF/
lgqRIcNGRSvVmEOp0MgPZOThFnEld2W1/8ch+9G6xzTXjDL09UKApbCKQ0fmqxbM
X8IODdXsiPx2yJgLv0Pm4mJopkJXlU4=
=3nFq
-----END PGP SIGNATURE-----
