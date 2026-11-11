# Portable source shared by game DLLs and freestanding WASM consumers.
add_library(morph-matrix-projection INTERFACE)
target_include_directories(morph-matrix-projection INTERFACE "${CMAKE_CURRENT_LIST_DIR}")
