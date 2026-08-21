#!/bin/bash
/home/kaushika/REPOS/llvm-project/build/bin/clang++ --target=riscv64-linux-gnu --sysroot=/home/kaushika/REPOS/riscv-support/sysroot-deb-riscv64-unstable/ -pthread -O2 $1.cpp -static -o $1
