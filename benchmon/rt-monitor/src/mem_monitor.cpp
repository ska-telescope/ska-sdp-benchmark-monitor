#include <chrono>
#include <fstream>
#include <thread>

#include "mem_monitor.h"
#include "monitor_io.h"

namespace rt_monitor::mem
{
void start(const double time_interval, const std::string &out_path, const bool &running)
{
    auto file = io::make_buffer(out_path);
    while (running)
    {
        const auto now = std::chrono::system_clock::now();
        const auto duration = now.time_since_epoch();
        const auto timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();
        io::write_binary(file, timestamp);

        std::ifstream input("/proc/meminfo");

        int i = 0;
        while (!input.eof() && i < 56)
        {
            ++i;
            std::string line;
            std::getline(input, line);
            auto value_start = line.find_first_of("0123456789");
            auto value_end = line.find_last_of("0123456789") + 1;
            uint64_t value = 0;
            if (value_start != std::string::npos)
            {
                for (auto it = line.begin() + value_start; it != line.begin() + value_end; ++it)
                {
                    value = value * 10 + static_cast<uint64_t>(*it - '0');
                }
            }
            io::write_binary(file, value);
        }
        std::this_thread::sleep_for(std::chrono::microseconds(static_cast<int64_t>(time_interval * 1000)));
#ifndef BINARY
        file << std::endl;
#endif
    }
}
} // namespace rt_monitor::mem