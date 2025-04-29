#include <gtest/gtest.h>

#include <cassert>
#include <iostream>
#include <type_traits>

// #include "base/bitunion.hh"
// #include "base/cprintf.hh"
#include "params/XYZCache.hh"
#include "xyz/XYZCacheMemory.hh"

using namespace gem5::ruby;

namespace {
    TEST(XYZCacheMemory, SimpleTest) {
        EXPECT_EQ(1, 2);
    }
}
