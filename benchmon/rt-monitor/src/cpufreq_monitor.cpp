#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <scn/scan.h>
#include <spdlog/spdlog.h>
#include <string>
#include <thread>
#include <vector>

#include "cpufreq_monitor.h"
#include "monitor_io.h"
#include "pause_manager.h"

namespace rt_monitor::cpufreq
{
std::vector<std::string> get_online_cpu_scaling_freq_paths()
{
    std::vector<std::pair<int, std::string>> indexed_paths;

    auto cpu_path_iterator = std::filesystem::directory_iterator("/sys/devices/system/cpu");
    for (const auto &entry : cpu_path_iterator)
    {
        if (entry.is_directory() && entry.path().filename().string().starts_with("cpu"))
        {
            std::string online_path = entry.path().string() + "/online";
            if (std::filesystem::exists(online_path))
            {
                std::ifstream online_file(online_path);
                int online_status;
                online_file >> online_status;
                if (online_status == 1)
                {
                    std::string scaling_freq_path = entry.path().string() + "/cpufreq/scaling_cur_freq";
                    if (std::filesystem::exists(scaling_freq_path))
                    {
                        int cpu_index = std::stoi(entry.path().filename().string().substr(3));
                        indexed_paths.emplace_back(cpu_index, scaling_freq_path);
                    }
                }
            }
        }
    }

    std::vector<std::string> paths;
    paths.reserve(indexed_paths.size());
    paths.emplace_back("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq");
    std::sort(indexed_paths.begin(), indexed_paths.end());
    for (const auto &[index, path] : indexed_paths)
    {
        paths.push_back(path);
    }
    return paths;
}

std::pair<uint64_t, uint64_t> get_freq_min_max()
{
    uint64_t min_freq = 0, max_freq = 0;

    std::string cpu0_path = "/sys/devices/system/cpu/cpu0/cpufreq/";
    std::ifstream min_freq_file(cpu0_path + "cpuinfo_min_freq");
    std::ifstream max_freq_file(cpu0_path + "cpuinfo_max_freq");

    if (min_freq_file.is_open())
    {
        min_freq_file >> min_freq;
    }

    if (max_freq_file.is_open())
    {
        max_freq_file >> max_freq;
    }

    return {min_freq, max_freq};
}

void start(const double time_interval, const std::string &out_path)
{
    auto file = io::make_buffer(out_path);

    const auto [freq_min, freq_max] = get_freq_min_max();
    io::write_binary(file, freq_min);
    io::write_binary(file, freq_max);

    const auto cpu_freq_paths = get_online_cpu_scaling_freq_paths();
    while (!pause_manager::stopped())
    {
        if (pause_manager::paused())
        {
            spdlog::trace("CPU frequency monitoring paused");
            std::unique_lock<std::mutex> lock(pause_manager::mutex());
            pause_manager::condition_variable().wait(lock, [] { return !pause_manager::paused().load(); });
        }
        
        spdlog::trace("reading a CPU frequency monitoring sample");
        const auto now = std::chrono::system_clock::now();
        const auto duration = now.time_since_epoch();
        const auto timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();

        for (uint32_t i = 0; i < cpu_freq_paths.size(); ++i)
        {
            const auto &path = cpu_freq_paths[i];
            std::ifstream freq_file(path);

            std::string line;
            std::getline(freq_file, line);
            const auto [frequency] = scn::scan<uint32_t>(line, "{}")->values();

            io::write_binary(file, timestamp);
            io::write_binary(file, i);
            io::write_binary(file, frequency);
        }
        std::this_thread::sleep_for(std::chrono::microseconds(static_cast<int64_t>(time_interval * 1000)));
    }
    spdlog::trace("CPU frequency monitoring stopped");
}
} // namespace rt_monitor::cpufreq