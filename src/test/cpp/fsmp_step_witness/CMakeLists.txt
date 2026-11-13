cmake_minimum_required(VERSION 3.25)
project(CLAWFSMPWitness VERSION 0.0.2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(claw-fsmp-witness-tests WitnessTests.cpp)
if(MSVC)
  target_compile_options(claw-fsmp-witness-tests PRIVATE /W4 /permissive- /UNDEBUG)
endif()
enable_testing()
add_test(NAME claw-fsmp-witness-pure COMMAND claw-fsmp-witness-tests)
# Native DLL build uses the separately recorded external build.py, verified
# source-built C5dd CommonLib, 2662 SDK files and 293 dependency-prefix files.
# No add_subdirectory from runtime, install(), provider edit or deployment rule.
