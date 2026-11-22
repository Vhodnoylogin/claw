cmake_minimum_required(VERSION 3.25)
project(CLAWFSMPPairContactTests LANGUAGES CXX)

add_executable(claw-fsmp-pair-contact-tests PairWindowTests.cpp)
target_compile_features(claw-fsmp-pair-contact-tests PRIVATE cxx_std_20)
if(MSVC)
  target_compile_options(claw-fsmp-pair-contact-tests PRIVATE /W4 /WX /permissive- /UNDEBUG)
else()
  target_compile_options(claw-fsmp-pair-contact-tests PRIVATE -Wall -Wextra -Werror -pedantic -UNDEBUG)
endif()

enable_testing()
add_test(NAME claw-fsmp-pair-contact-window COMMAND claw-fsmp-pair-contact-tests)
