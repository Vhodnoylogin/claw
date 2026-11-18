cmake_minimum_required(VERSION 3.25)
project(CLAWGeometryWitness VERSION 0.0.1 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(claw-geometry-tests GeometryTests.cpp)
if(MSVC)
  target_compile_options(claw-geometry-tests PRIVATE /W4 /permissive- /UNDEBUG)
endif()
enable_testing()
add_test(NAME claw-geometry-pure COMMAND claw-geometry-tests)
# The separately pinned external build recipe selects the native SE-only SDK
# translation unit and dependencies. No production add_subdirectory/install rule.
