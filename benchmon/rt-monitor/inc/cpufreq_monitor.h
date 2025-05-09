#pragma once
#include <string>

/**
 * @file cpufreq_monitor.h
 * @brief Namespace for CPU cores frequency monitoring functionality within the real-time monitor module.
 */
namespace rt_monitor::cpufreq
{
/**
 * @brief Starts the CPU frequency monitoring process.
 *
 * This function initiates the monitoring of CPU cores frequency with a specified time interval and writes the results to the
 * specified output path. The monitoring process continues as long as the provided running flag remains true.
 *
 * @param time_interval The time interval (in seconds) between each CPU frequency measurement.
 * @param out_path The file path where the monitoring data will be saved.
 * @param running A reference to a boolean flag that controls the monitoring process. Monitoring continues as long as
 * this flag is true.
 */
void start(const double time_interval, const std::string &out_path);
} // namespace rt_monitor::cpufreq