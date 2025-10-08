#pragma once
#include <string>

/**
 * @file mom_monitor.h
 * @namespace rt_monitor::net
 * @brief Namespace for network usage monitoring functionality within the real-time monitor module.
 */
namespace rt_monitor::net
{
/**
 * @brief Starts the network monitoring process.
 *
 * This function initiates the monitoring of network traffic at a specified time interval and writes the monitoring data
 * to a specified stream that can either be a file stream of a Grafana DB stream.
 *
 * @param time_interval The time interval (in seconds) between each monitoring sample.
 * @param stream The stream to output monitoring data to. Can either be a file stream or a Grafana DB stream.
 */
template <typename stream_type> void start_sampling(const double time_interval, stream_type &&stream);
} // namespace rt_monitor::net
