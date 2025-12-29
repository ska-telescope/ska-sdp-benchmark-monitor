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
    "inc/ib_monitor.h"
    "inc/variable_monitor.h"
    "inc/thread_safe_queue.hpp")

set(source_files
    "src/cpu_monitor.cpp"
    "src/cpufreq_monitor.cpp"
    "src/disk_monitor.cpp"
    "src/mem_monitor.cpp"
    "src/main.cpp"
    "src/monitor_io.cpp"
    "src/net_monitor.cpp"
    "src/ib_monitor.cpp"
    "src/pause_manager.cpp"
    "src/variable_monitor.cpp")

add_executable(rt-monitor ${header_files} ${source_files})
target_include_directories(rt-monitor PUBLIC inc)
# target_link_libraries(rt-monitor PRIVATE scn::scn)
target_link_libraries(rt-monitor PRIVATE spdlog::spdlog)
target_link_libraries(rt-monitor PRIVATE CURL::libcurl)
# target_link_libraries(rt-monitor PRIVATE InfluxData::InfluxDB)
if(ICU_FOUND)
  target_link_libraries(rt-monitor PRIVATE ICU::uc ICU::data ICU::i18n)
endif()

install(TARGETS rt-monitor DESTINATION .)


