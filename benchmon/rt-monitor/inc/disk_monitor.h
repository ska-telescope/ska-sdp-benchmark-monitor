#pragma once
#include <string>

/**
 * @file disk_monitor.h
 * @brief Namespace for disk usage monitoring functionality within the real-time monitor module.
 */
namespace rt_monitor::disk
{
/**
 * @brief Starts the disk monitoring process.
 *
 * This function initiates the monitoring of disk usage at a specified time interval and writes the monitoring data to
 * the specified output path. The monitoring process continues as long as the provided running flag remains true.
 *
 * @param time_interval The time interval (in seconds) between each monitoring sample.
 * @param out_path The file path where the monitoring data will be written.
 * @param running A reference to a boolean flag that controls the monitoring process. Monitoring continues as long as
 * this flag is true.
 */
void start(const double time_interval, const std::string &out_path);
} // namespace rt_monitor::disk