#include "net_monitor.h"
#include "db_stream.hpp"
#include "file_stream.hpp"
#include "monitor_io.h"
#include "pause_manager.h"
#include <chrono>

namespace rt_monitor::net
{
struct rate_sample
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    long long int transferred{0};
    long long int received{0};
};

struct data_sample
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    long long int transferred{0};
    long long int received{0};

    data_sample &operator+=(const data_sample &other)
    {
        transferred += other.transferred;
        received += other.received;
        return *this;
    }

    data_sample operator+(const data_sample &other) const
    {
        data_sample result = *this;
        result += other;
        return result;
    }

    rate_sample operator-(const data_sample &other) const
    {
        rate_sample result;
        result.timestamp = this->timestamp;
        const double dt = std::chrono::duration_cast<std::chrono::nanoseconds>(
                              this->timestamp - other.timestamp).count() / 1e9;
        if (dt <= 0.0)
        {
            // Return zero rates if time interval is non-positive
            result.transferred = 0;
            result.received    = 0;
            return result;
        }
        result.transferred = static_cast<long long int>(
                                 static_cast<double>(this->transferred - other.transferred)
                                 / (1024.0 * dt));
        result.received    = static_cast<long long int>(
                                 static_cast<double>(this->received - other.received)
                                 / (1024.0 * dt));
        return result;
    }
};
} // namespace rt_monitor::net

namespace rt_monitor
{
template <> db_stream &db_stream::operator<< <net::rate_sample>(net::rate_sample sample)
{
    influxdb::Point point{"net"};
    point.addField("Transfer(kiB/s)", sample.transferred)
        .addField("Receive(kiB/s)", sample.received)
        .setTimestamp(sample.timestamp);

    try
    {
        this->db_ptr_->write(std::move(point));
    }
    catch (const std::runtime_error &e)
    {
        spdlog::error(std::string{"Error while pushing a network sample: "} + e.what());
    }
    return *this;
}
} // namespace rt_monitor

namespace rt_monitor::net
{
data_sample read_cumulated_sample()
{
    net::data_sample sample;
    std::ifstream input("/proc/net/dev");
    if (!input.is_open())
    {
        spdlog::error("Failed to open /proc/net/dev");
        return sample;
    }

    std::string line;
    int line_number = 0;
    const auto now = std::chrono::system_clock::now();
    sample.timestamp = now;

    while (std::getline(input, line))
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

        sample.received += received;
        sample.transferred += transferred;
    }

    return sample;
}

void process_net_sample(std::ostream &file)
{
    spdlog::trace("reading a network monitoring sample");
    const auto now = std::chrono::system_clock::now();
    const auto duration = now.time_since_epoch();
    const auto timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();

    std::ifstream input("/proc/net/dev");

    std::string line;
    int line_number = 0;
    while (std::getline(input, line))
    {
        ++line_number;
        if (line_number <= 2)
        {
            continue;
        }

        io::write_binary(file, timestamp);

        std::istringstream line_stream(line);
        std::string token;
        while (line_stream >> token)
        {
            if (token.back() == ':')
            {
                token.pop_back();
                std::array<char, 32> interface_char;
                std::fill(interface_char.begin(), interface_char.end(), '\0');
                const size_t interface_char_size = std::min(interface_char.size(), token.size());
                std::copy_n(token.cbegin(), interface_char_size, interface_char.begin());
                io::write_binary(file, interface_char);
                continue;
            }
            try
            {
                uint64_t value = std::stoull(token);
                io::write_binary(file, value);
            }
            catch (const std::invalid_argument &)
            {
                spdlog::error("invalid input in /proc/net/dev");
            }
        }
    }
}

template <> void start_sampling(const double time_interval, db_stream &&stream)
{
    bool sampling_warning_provided = false;
    std::array<data_sample, 2> samples;
    size_t last_index = 0;
    samples[last_index] = read_cumulated_sample();
    std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int64_t>(time_interval)));

    while (!pause_manager::stopped())
    {
        if (pause_manager::paused())
        {
            spdlog::trace("network monitoring paused");
            std::unique_lock<std::mutex> lock(pause_manager::mutex());
            pause_manager::condition_variable().wait(lock, [] { return !pause_manager::paused().load(); });
        }

        const auto begin = std::chrono::high_resolution_clock::now();

        auto &last_sample = samples[last_index];
        auto &current_sample = samples[1 - last_index];

        current_sample = read_cumulated_sample();
        const auto diff_sample = current_sample - last_sample;
        stream << diff_sample;

        const auto end = std::chrono::high_resolution_clock::now();
        const auto sampling_time = std::chrono::duration_cast<std::chrono::milliseconds>(end - begin).count();

        last_index = 1 - last_index;
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

        std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int64_t>(time_to_wait)));
    }
    spdlog::trace("network monitoring stopped");
}

template <> void start_sampling(const double time_interval, file_stream &&stream)
{
    bool sampling_warning_provided = false;

    auto &file = stream.get_file();
    while (!pause_manager::stopped())
    {
        if (pause_manager::paused())
        {
            spdlog::trace("network monitoring paused");
            std::unique_lock<std::mutex> lock(pause_manager::mutex());
            pause_manager::condition_variable().wait(lock, [] { return !pause_manager::paused().load(); });
        }

        const auto begin = std::chrono::high_resolution_clock::now();
        process_net_sample(file);
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

        std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int64_t>(time_to_wait)));
    }
    spdlog::trace("network monitoring stopped");
}
} // namespace rt_monitor::net
