#pragma once

/**
 * @file cpufreq_monitor.h
 * @namespace rt_monitor::cpufreq
 * @brief Namespace for CPU cores frequency monitoring functionality within the real-time monitor module.
 */
namespace rt_monitor::cpufreq
{
/**
 * @brief Starts the CPU frequency monitoring process.
 *
 * This function initiates the monitoring of CPU cores frequency with a specified time interval and writes the results
 * to a specified stream that can either be a file stream of a Grafana DB stream.
 *
 * @param time_interval The time interval (in seconds) between each CPU frequency measurement.
 * @param stream The stream to output monitoring data to. Can either be a file stream or a Grafana DB stream.
 */
template <typename stream_type> void start_sampling(double time_interval, stream_type &&stream);
} // namespace rt_monitor::cpufreq