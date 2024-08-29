cmake_minimum_required(VERSION 3.15)
project(test_package CXX)

find_package(wxWidgets CONFIG REQUIRED COMPONENTS core base OPTIONAL_COMPONENTS stc)

if(MSVC)
  add_compile_definitions(UNICODE)
  add_compile_definitions(_UNICODE)
  add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
endif()

add_executable(${PROJECT_NAME} test_package.cpp)
if(TARGET wx::stc)
    target_link_libraries(${PROJECT_NAME} wx::stc)
endif()
target_link_libraries(${PROJECT_NAME} wx::core)
