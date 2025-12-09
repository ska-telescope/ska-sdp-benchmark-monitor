#pragma once

/**
 * @file cpu_monitor.h
 * @namespace rt_monitor::cpu
 * @brief Namespace for CPU monitoring functionality within the real-time monitor module.
 */
namespace rt_monitor::cpu
{
/**
 * @brief Starts the CPU monitoring process.
 *
 * This function initiates the monitoring of CPU usage with a specified time interval and writes the results to a
 * specified stream that can either be a file stream or a Grafana DB stream.
 *
 * @param time_interval The time interval (in seconds) between each CPU usage measurement.
 * @param stream The stream to output monitoring data to. Can either be a file stream or a Grafana DB stream.
 */
template <typename stream_type> void start_sampling(double time_interval, stream_type &&stream);
} // namespace rt_monitor::cpu
