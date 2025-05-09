#include <array>
#include <chrono>
#include <fstream>
#include <spdlog/spdlog.h>
#include <thread>

#include "mem_monitor.h"
#include "monitor_io.h"
#include "pause_manager.h"

namespace rt_monitor::mem
{
constexpr size_t n_fields = 55;
constexpr std::array<bool, n_fields> enabled{
    true,  true,  false, true,  true,  true,  false, false, false, false, false, false, false, false,
    true,  true,  false, false, false, false, false, false, false, false, true,  false, false, false,
    false, false, false, false, false, false, false, false, false, false, false, false, false, false,
    false, false, false, false, false, false, false, false, false, false, false, false, false};

void start(const double time_interval, const std::string &out_path)
{
    auto file = io::make_buffer(out_path);
    while (!pause_manager::stopped())
    {
        if (pause_manager::paused())
        {
            spdlog::trace("memory monitoring paused");
            std::unique_lock<std::mutex> lock(pause_manager::mutex());
            pause_manager::condition_variable().wait(lock, [] { return !pause_manager::paused().load(); });
        }
        size_t size = 0;
        spdlog::trace("reading a memory monitoring sample");
        const auto now = std::chrono::system_clock::now();
        const auto duration = now.time_since_epoch();
        const auto timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();
        io::write_binary(file, timestamp);
        size += sizeof(timestamp);

        std::ifstream input("/proc/meminfo");

        int i = 0;
        while (!input.eof() && i < 55)
        {
            std::string line;
            std::getline(input, line);
            if (enabled[i])
            {
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
                size += sizeof(value);
            }
            ++i;
        }
        std::this_thread::sleep_for(std::chrono::microseconds(static_cast<int64_t>(time_interval * 1000)));
#ifndef BINARY
        file << std::endl;
#endif
    }
    spdlog::trace("memory monitoring stopped");
}
} // namespace rt_monitor::mem