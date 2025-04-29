#pragma once
#include <string>

/**
 * @namespace rt_monitor::cpu
 * @brief Namespace for CPU monitoring functionality within the real-time monitor module.
 */
namespace rt_monitor::cpu
{
/**
 * @brief Starts the CPU monitoring process.
 *
 * This function initiates the monitoring of CPU usage with a specified time interval and writes the results to the
 * specified output path. The monitoring process continues as long as the provided running flag remains true.
 *
 * @param time_interval The time interval (in seconds) between each CPU usage measurement.
 * @param out_path The file path where the monitoring results will be written.
 * @param running A reference to a boolean flag that controls the monitoring process. Monitoring continues as long as
 * this flag is true.
 */
void start(const double time_interval, const std::string &out_path, const bool &running);
} // namespace rt_monitor::cpu
