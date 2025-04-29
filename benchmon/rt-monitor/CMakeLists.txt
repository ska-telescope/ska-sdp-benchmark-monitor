cmake_minimum_required(VERSION 3.10)

project(rt-monitor)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(header_files "inc/cpu_monitor.h"
                 "inc/cpufreq_monitor.h"
                 "inc/disk_monitor.h"
                 "inc/mem_monitor.h"
                 "inc/monitor_io.h"
                 "inc/net_monitor.h")
set(source_files "src/cpu_monitor.cpp"
                 "src/cpufreq_monitor.cpp"
                 "src/disk_monitor.cpp"
                 "src/mem_monitor.cpp"
                 "src/main.cpp"
                 "src/monitor_io.cpp"
                 "src/net_monitor.cpp")

add_executable(rt-monitor ${header_files} ${source_files})

target_include_directories(rt-monitor PUBLIC inc)

find_package(fmt REQUIRED)
target_link_libraries(rt-monitor PRIVATE fmt::fmt)

find_package(scn REQUIRED)
target_link_libraries(rt-monitor PRIVATE scn::scn)