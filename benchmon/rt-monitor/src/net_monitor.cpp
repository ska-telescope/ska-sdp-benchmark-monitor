#include "net_monitor.h"
#include "db_stream.hpp"
#include "file_stream.hpp"
#include "monitor_io.h"
#include "pause_manager.h"
#include "thread_safe_queue.hpp"
#include <chrono>
#include <sstream>
#include <thread>
#include <fcntl.h>
#include <unistd.h>
#include <vector>
#include <cstring>

namespace rt_monitor::net
{
struct interface_data
{
    std::string name;
    long long int transferred{0};
    long long int received{0};
};

struct data_sample
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    std::vector<interface_data> interfaces;
};

struct rate_sample
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    std::string name;
    long long int transferred{0};
    long long int received{0};
};

} // namespace rt_monitor::net

namespace rt_monitor
{
template <> db_stream &db_stream::operator<< <net::data_sample>(net::data_sample sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    for (const auto& iface : sample.interfaces) {
        std::stringstream ss;
        ss << "network_stats,hostname=" << hostname << ",interface=" << iface.name << " ";
        ss << "tx_bytes=" << iface.transferred << "i,"
           << "rx_bytes=" << iface.received << "i";
        ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
        this->write_line(ss.str());
        
        spdlog::debug("Sending network sample for interface {} to InfluxDB", iface.name);
    }
    return *this;
}

template <> db_stream &db_stream::operator<< <std::vector<net::rate_sample>>(std::vector<net::rate_sample> samples)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    for (const auto& sample : samples) {
        std::stringstream ss;
        ss << "network,hostname=" << hostname << ",interface=" << sample.name << " ";
        ss << "tx_bytes=" << sample.transferred << "i,"
           << "rx_bytes=" << sample.received << "i";
        ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
        this->write_line(ss.str());
    }
    return *this;
}
} // namespace rt_monitor

namespace rt_monitor::net
{
data_sample read_cumulated_sample(int fd)
{
    net::data_sample sample;
    const auto now = std::chrono::system_clock::now();
    sample.timestamp = now;

    if (lseek(fd, 0, SEEK_SET) == -1) return sample;

    char buffer[16384]; // 16KB should be enough for /proc/net/dev
    ssize_t bytes_read = read(fd, buffer, sizeof(buffer) - 1);
    if (bytes_read <= 0) return sample;
    buffer[bytes_read] = '\0';

    std::string content(buffer);
    std::istringstream iss(content);
    std::string line;
    int line_number = 0;

    while (std::getline(iss, line))
    {
        ++line_number;
        if (line_number <= 2)
        {
            continue; // Skip headers
        }

        std::istringstream line_stream(line);
        std::string iface_token;
        if (!(line_stream >> iface_token))
            continue;

        // Remove trailing ':' from interface name
        if (iface_token.back() == ':')
            iface_token.pop_back();

        // Read receive bytes (first value after interface name)
        std::string value_token;
        if (!(line_stream >> value_token))
            continue;

        long long int received = 0;
        try
        {
            received = std::stoll(value_token);
        }
        catch (const std::exception &)
        {
            spdlog::error("Failed to parse received bytes for interface {}", iface_token);
            continue;
        }

        // Skip next 7 tokens to get to the transmit bytes (9th column)
        for (int i = 0; i < 7; ++i)
        {
            if (!(line_stream >> value_token))
                break;
        }

        long long int transferred = 0;
        if (line_stream >> value_token)
        {
            try
            {
                transferred = std::stoll(value_token);
            }
            catch (const std::exception &)
            {
                spdlog::error("Failed to parse transferred bytes for interface {}", iface_token);
                continue;
            }
        }

        sample.interfaces.push_back({iface_token, transferred, received});
    }

    return sample;
}

void net_producer(double time_interval, ThreadSafeQueue<data_sample>& queue)
{
    int fd = open("/proc/net/dev", O_RDONLY);
    if (fd < 0) {
        spdlog::error("Failed to open /proc/net/dev");
        queue.stop();
        return;
    }

    bool sampling_warning_provided = false;
    while (!pause_manager::stopped())
    {
        pause_manager::wait_if_paused();

        const auto begin = std::chrono::high_resolution_clock::now();
        
        auto sample = read_cumulated_sample(fd);
        spdlog::debug("Collected network sample with {} interfaces", sample.interfaces.size());
        queue.push(std::move(sample));

        const auto end = std::chrono::high_resolution_clock::now();
        const auto sampling_time = std::chrono::duration_cast<std::chrono::milliseconds>(end - begin).count();
        auto time_to_wait = time_interval - sampling_time;
        if (time_to_wait < 0.)
        {
            if (!sampling_warning_provided)
            {
                spdlog::warn(
                    "The sampling period of {} ms might be too low for network monitoring. The last sampling time "
                    "was {} ms. Samples might be missed. Consider reducing the sampling frequency.",
                    static_cast<int>(time_interval), sampling_time);
                sampling_warning_provided = true;
            }
            time_to_wait = 0.;
        }

        pause_manager::sleep_for(std::chrono::milliseconds(static_cast<int64_t>(time_to_wait)));
    }
    close(fd);
    queue.stop();
    spdlog::trace("network producer stopped");
}

template <> void start_sampling(const double time_interval, db_stream &&stream)
{
    ThreadSafeQueue<data_sample> queue;
    std::thread producer_thread(net_producer, time_interval, std::ref(queue));

    data_sample sample;
    while (queue.pop(sample))
    {
        if (pause_manager::stopped()) break;
        stream << sample;
    }
    
    producer_thread.join();
    spdlog::trace("network monitoring stopped");
}

template <> void start_sampling(const double time_interval, file_stream &&stream)
{
    ThreadSafeQueue<data_sample> queue;
    std::thread producer_thread(net_producer, time_interval, std::ref(queue));

    auto &file = stream.get_file();
    data_sample sample;
    while (queue.pop(sample))
    {
        if (pause_manager::stopped()) break;
        io::write_binary(file, sample.timestamp.time_since_epoch().count());
        for (const auto& iface : sample.interfaces) {
             io::write_binary(file, iface.name);
             io::write_binary(file, iface.received);
             io::write_binary(file, iface.transferred);
        }
    }
    producer_thread.join();
    spdlog::trace("network monitoring stopped");
}
} // namespace rt_monitor::net
