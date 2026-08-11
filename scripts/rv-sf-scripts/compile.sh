#!/bin/bash
/home/kaushika/REPOS/riscv-support/riscv-cross-compiler/riscv/bin/riscv64-unknown-linux-gnu-g++ -g -O2 -I/home/kaushika/REPOS/riscv-support/riscv-cross-compiler/riscv/riscv64-unknown-linux-gnu/include/c++/14.2.0 -static $1.cpp -lpthread -o $1
