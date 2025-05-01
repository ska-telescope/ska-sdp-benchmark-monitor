#include <chrono>
#include <cstdint>
#include <fstream>
#include <ostream>
#include <sched.h>
#include <scn/scan.h>
#include <thread>

#include <iostream>

#include "cpu_monitor.h"
#include "monitor_io.h"

namespace rt_monitor::cpu
{
std::ostream &read_cpu(std::ostream &stream)
{
    const auto now = std::chrono::system_clock::now();
    const auto duration = now.time_since_epoch();
    const uint64_t timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();

    std::ifstream file("/proc/stat");
    std::string line;
    while (std::getline(file, line))
    {
        if (!line.starts_with("cpu"))
            break;

        const auto result = scn::scan<std::string, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t,
                                      uint32_t, uint32_t, uint32_t>(line, "{} {} {} {} {} {} {} {} {} {} {}");
        if (!result)
            continue;
        const auto [cpuid_value, user_value, nice_value, system_value, idle_value, iowait_value, irq_value,
                    softirq_value, steal_value, guest_value, guestnice_value] = result->values();
        const auto cpuid = io::cpuid_str_to_uint(cpuid_value);

        io::write_binary(stream, timestamp);
        io::write_binary(stream, cpuid);
        io::write_binary(stream, user_value);
        io::write_binary(stream, nice_value);
        io::write_binary(stream, system_value);
        io::write_binary(stream, idle_value);
        io::write_binary(stream, iowait_value);
        io::write_binary(stream, irq_value);
        io::write_binary(stream, softirq_value);
        io::write_binary(stream, steal_value);
        io::write_binary(stream, guest_value);
        io::write_binary(stream, guestnice_value);
    }

    return stream;
}

void start(const double time_interval, const std::string &out_path, const bool &running)
{
    auto file = io::make_buffer(out_path);
    while (running)
    {
        read_cpu(file);
        std::this_thread::sleep_for(std::chrono::microseconds(static_cast<int64_t>(time_interval * 1000)));
    }
}
} // namespace rt_monitor::cpu