#!/bin/bash
/home/kaushika/REPOS/riscv-support/riscv-cross-compiler/riscv/bin/riscv64-unknown-linux-gnu-g++ -g -O2 \
  -I/home/kaushika/REPOS/riscv-support/riscv-cross-compiler/riscv/riscv64-unknown-linux-gnu/include/c++/14.2.0 \
  -I/home/kaushika/REPOS/yu-gem5/gem5/include/ \
  -static \
  $1.cpp \
  -lpthread /home/kaushika/REPOS/yu-gem5/gem5/util/m5/build/riscv/out/libm5.a \
  -o $1
