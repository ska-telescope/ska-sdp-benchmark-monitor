#include <csignal>
#include <future>
#include <mutex>
#include <spdlog/spdlog.h>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "cpu_monitor.h"
#include "cpufreq_monitor.h"
#include "disk_monitor.h"
#include "mem_monitor.h"
#include "net_monitor.h"
#include "pause_manager.h"
#include "spdlog/common.h"
#include "spdlog/logger.h"

namespace rt_monitor
{
struct monitor_config
{
    bool enable_cpu = false;
    bool enable_cpufreq = false;
    bool enable_disk = false;
    bool enable_mem = false;
    bool enable_net = false;
    double sampling_frequency = 0.0;
    spdlog::level::level_enum log_level = spdlog::level::err;
    std::unordered_map<std::string, std::string> output_files;
};

void signal_handler(const int signal)
{
    if (signal == SIGUSR1)
    {
        pause_manager::pause();
    }
    else if (signal == SIGUSR2)
    {
        pause_manager::resume();
    }
    else if (signal == SIGINT)
    {
        pause_manager::stop();
    }
}

spdlog::level::level_enum parse_log_level(const std::string &level_str)
{
    static const std::unordered_map<std::string, spdlog::level::level_enum> levels = {
        {"trace", spdlog::level::trace},       {"debug", spdlog::level::debug}, {"info", spdlog::level::info},
        {"warn", spdlog::level::warn},         {"error", spdlog::level::err},   {"err", spdlog::level::err},
        {"critical", spdlog::level::critical}, {"off", spdlog::level::off}};

    auto it = levels.find(level_str);
    if (it != levels.end())
    {
        return it->second;
    }
    return spdlog::level::warn; // fallback
}

monitor_config parse_arguments(int argc, char **argv)
{
    if (argc < 3)
    {
        spdlog::error("Usage: {} sampling-frequency <Hz> [--cpu <cpu_output_file_path>] [--cpu-freq <cpu_freq_output_file_path>] "
               "[--disk <disk_output_file_path>] [--mem <mem_output_file_path>] [--net <net_output_file_path>] "
               "[--log-level <trace/debug/info/warn/error/critical/off]", argv[0]);
        spdlog::error("Example: {} sampling-frequency 100 --cpu cpu_output.bin --cpu-freq cpu_freq_output.bin "
                     "--disk disk_output.bin --mem mem_output.bin --net net_output.bin", argv[0]);
        exit(1);
    }

    monitor_config config;
    for (int i = 1; i < argc; ++i)
    {
        std::string arg = argv[i];
        if (arg == "--sampling-frequency")
        {
            if (i + 1 >= argc)
            {
                throw std::invalid_argument("Missing value for --sampling-frequency");
            }
            config.sampling_frequency = std::stod(argv[++i]);
            if (config.sampling_frequency <= 0)
            {
                throw std::invalid_argument("Sampling frequency must be greater than 0");
            }
        }
        else if (arg == "--cpu")
        {
            if (i + 1 >= argc)
            {
                throw std::invalid_argument("Missing value for --cpu");
            }
            config.enable_cpu = true;
            config.output_files["cpu"] = argv[++i];
        }
        else if (arg == "--cpu-freq")
        {
            if (i + 1 >= argc)
            {
                throw std::invalid_argument("Missing value for --cpu-freq");
            }
            config.enable_cpufreq = true;
            config.output_files["cpu-freq"] = argv[++i];
        }
        else if (arg == "--disk")
        {
            if (i + 1 >= argc)
            {
                throw std::invalid_argument("Missing value for --disk");
            }
            config.enable_disk = true;
            config.output_files["disk"] = argv[++i];
        }
        else if (arg == "--mem")
        {
            if (i + 1 >= argc)
            {
                throw std::invalid_argument("Missing value for --mem");
            }
            config.enable_mem = true;
            config.output_files["mem"] = argv[++i];
        }
        else if (arg == "--net")
        {
            if (i + 1 >= argc)
            {
                throw std::invalid_argument("Missing value for --net");
            }
            config.enable_net = true;
            config.output_files["net"] = argv[++i];
        }
        else if (arg == "--log-level")
        {
            if (i + 1 >= argc)
            {
                throw std::invalid_argument("Missing value for --log-level");
            }
            config.log_level = parse_log_level(argv[++i]);
        }
        else
        {
            throw std::invalid_argument("Unknown argument: " + arg);
        }
    }

    if (config.sampling_frequency == 0.0)
    {
        throw std::invalid_argument("--sampling-frequency is required");
    }

    return config;
}
} // namespace rt_monitor

int main(int argc, char **argv)
{
    using namespace rt_monitor;
    std::mutex pause_mutex;

    try
    {
        monitor_config config;
        if (const char *env_p = std::getenv("RT_MONITOR_LOG_LEVEL"))
        {
            config.log_level = parse_log_level(env_p);
        }
        try
        {
            config = parse_arguments(argc, argv);
        }
        catch (std::invalid_argument error)
        {
            spdlog::error(error.what());
            return -1;
        }
        const double time_interval = 1000.0 / config.sampling_frequency;

        spdlog::set_level(config.log_level);
        spdlog::set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%^%l%$] [benchmon::rt-monitor] %v");

        signal(SIGUSR1, signal_handler);
        signal(SIGUSR2, signal_handler);
        signal(SIGINT, signal_handler);

        std::vector<std::future<void>> tasks;
        if (config.enable_cpu)
        {
            tasks.emplace_back(std::async(
                std::launch::async, [&]() { rt_monitor::cpu::start(time_interval, config.output_files["cpu"]); }));
        }
        if (config.enable_cpufreq)
        {
            tasks.emplace_back(std::async(std::launch::async, [&]() {
                rt_monitor::cpufreq::start(time_interval, config.output_files["cpu-freq"]);
            }));
        }
        if (config.enable_disk)
        {
            tasks.emplace_back(std::async(
                std::launch::async, [&]() { rt_monitor::disk::start(time_interval, config.output_files["disk"]); }));
        }
        if (config.enable_mem)
        {
            tasks.emplace_back(std::async(
                std::launch::async, [&]() { rt_monitor::mem::start(time_interval, config.output_files["mem"]); }));
        }
        if (config.enable_net)
        {
            tasks.emplace_back(std::async(
                std::launch::async, [&]() { rt_monitor::net::start(time_interval, config.output_files["net"]); }));
        }

        pause_manager::resume();

        for (auto &task : tasks)
        {
            task.wait();
        }
    }
    catch (const std::exception &e)
    {
        spdlog::error(e.what());
        return 1;
    }

    return 0;
}
