#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
#include <spdlog/spdlog.h>
#include <sstream>
#include <thread>

#include "monitor_io.h"
#include "net_monitor.h"
#include "pause_manager.h"

namespace rt_monitor::net
{
void read_net_sample(std::ostream &file)
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

void start(const double time_interval, const std::string &out_path)
{
    bool sampling_warning_provided = false;

    auto file = io::make_buffer(out_path);
    while (!pause_manager::stopped())
    {
        if (pause_manager::paused())
        {
            spdlog::trace("network monitoring paused");
            std::unique_lock<std::mutex> lock(pause_manager::mutex());
            pause_manager::condition_variable().wait(lock, [] { return !pause_manager::paused().load(); });
        }

        const auto begin = std::chrono::high_resolution_clock::now();
        read_net_sample(file);
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
