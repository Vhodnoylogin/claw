cmake_minimum_required(VERSION 3.25)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
    message(FATAL_ERROR "Use an out-of-source build directory such as target/native")
endif()
project(CLAW LANGUAGES CXX)

# Source is kept under src/main; all generated files belong in an out-of-source
# build such as target/native. Tests are separate from the shipping source tree.
option(CLAW_BUILD_TESTS "Build offline core tests (do not execute automatically)" OFF)
if(CLAW_BUILD_TESTS)
    enable_testing()
endif()
add_subdirectory(src/main/cpp)
