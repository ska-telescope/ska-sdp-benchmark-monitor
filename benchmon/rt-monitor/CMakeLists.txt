cmake_minimum_required(VERSION 3.10)

project(rt-monitor)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(dependencies)

set(header_files
    "inc/cpu_monitor.h"
    "inc/cpufreq_monitor.h"
    "inc/disk_monitor.h"
    "inc/mem_monitor.h"
    "inc/monitor_io.h"
    "inc/net_monitor.h"
    "inc/net_monitor.h")

set(source_files
    "src/cpu_monitor.cpp"
    "src/cpufreq_monitor.cpp"
    "src/disk_monitor.cpp"
    "src/mem_monitor.cpp"
    "src/main.cpp"
    "src/monitor_io.cpp"
    "src/net_monitor.cpp"
    "src/pause_manager.cpp")

add_executable(rt-monitor ${header_files} ${source_files})
target_include_directories(rt-monitor PUBLIC inc)
target_link_libraries(rt-monitor PRIVATE scn::scn)
target_link_libraries(rt-monitor PRIVATE spdlog::spdlog)
target_link_libraries(rt-monitor PRIVATE InfluxData::InfluxDB)

install(TARGETS rt-monitor DESTINATION .)

install(IMPORTED_RUNTIME_ARTIFACTS rt-monitor RUNTIME_DEPENDENCY_SET
        rt-monitor_dependency_set)

install(
  RUNTIME_DEPENDENCY_SET
  rt-monitor_dependency_set
  POST_EXCLUDE_REGEXES
  "${CMAKE_INSTALL_PREFIX}/lib"
  RUNTIME
  DESTINATION
  .)
