#pragma once

/**
 * @file mem_monitor.h
 * @namespace rt_monitor::mem
 * @brief Namespace for disk usage monitoring functionality within the real-time monitor module.
 */
namespace rt_monitor::mem
{
/**
 * @brief Starts the memory usage monitoring process.
 *
 * This function initiates the monitoring of memory usage at a specified time interval and writes the monitoring data to
 * a specified stream that can either be a file stream of a Grafana DB stream.
 *
 * @param time_interval The time interval (in seconds) between each monitoring sample.
 * @param stream The stream to output monitoring data to. Can either be a file stream or a Grafana DB stream.
 */
template <typename stream_type> void start_sampling(double time_interval, stream_type &&stream);
} // namespace rt_monitor::mem
