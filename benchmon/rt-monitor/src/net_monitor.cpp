#include <chrono>
#include <fstream>
#include <iostream>
#include <thread>

#include "monitor_io.h"
#include "net_monitor.h"

namespace rt_monitor::net
{
void start(const double time_interval, const std::string &out_path, const bool &running)
{
    auto file = io::make_buffer(out_path);
    while (running)
    {
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
                    io::write_binary(file, token);
                    continue;
                }
                try
                {
                    uint64_t value = std::stoull(token);
                    io::write_binary(file, value);
                }
                catch (const std::invalid_argument &)
                {
                    std::cerr << "Invalid input in /proc/net/dev" << std::endl;
                }
            }
#ifndef BINARY
            file << std::endl;
#endif
        }

        std::this_thread::sleep_for(std::chrono::microseconds(static_cast<int64_t>(time_interval * 1000)));
    }
}
} // namespace rt_monitor::net