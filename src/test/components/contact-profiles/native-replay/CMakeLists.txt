cmake_minimum_required(VERSION 3.25)
project(claw_posed_support_replay LANGUAGES CXX)

set(CLAW_POSE_BENCH_INPUT_DIR "" CACHE PATH "External directory with the exact exported observations.h")
if(NOT EXISTS "${CLAW_POSE_BENCH_INPUT_DIR}/observations.h")
    message(FATAL_ERROR "Export the reviewed VR65 fixture with export_pose_fit_benchmark.py first")
endif()

add_executable(claw_pose_support ../pose_fit_benchmark.cpp)
target_compile_features(claw_pose_support PRIVATE cxx_std_20)
target_include_directories(claw_pose_support PRIVATE
    "../../../../main/cpp/include" "${CLAW_POSE_BENCH_INPUT_DIR}")
if(MSVC)
    target_compile_options(claw_pose_support PRIVATE /fp:precise /W4 /WX)
endif()
