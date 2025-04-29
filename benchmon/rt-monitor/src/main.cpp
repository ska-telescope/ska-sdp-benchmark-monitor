#include <csignal>
#include <future>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "cpu_monitor.h"
#include "cpufreq_monitor.h"
#include "disk_monitor.h"
#include "mem_monitor.h"
#include "net_monitor.h"

static bool running = true;

void signal_handler(const int signal)
{
    running = false;
}

struct monitor_config
{
    bool enable_cpu = false;
    bool enable_cpufreq = false;
    bool enable_disk = false;
    bool enable_mem = false;
    bool enable_net = false;
    double sampling_frequency = 0.0;
    std::unordered_map<std::string, std::string> output_files;
};

monitor_config parse_arguments(int argc, char **argv)
{
    if (argc < 3)
    {
        std::cerr
            << "Usage: " << argv[0]
            << " --sampling-frequency <Hz> [--cpu <cpu_output_file_path>] [--cpu-freq <cpu_freq_output_file_path>] "
               "[--disk <disk_output_file_path>] [--mem <mem_output_file_path>] [--net <net_output_file_path>]"
            << std::endl;
        std::cerr << "Example: " << argv[0]
                  << " --sampling-frequency 100 --cpu cpu_output.bin --cpu-freq cpu_freq_output.bin "
                     "--disk disk_output.bin --mem mem_output.bin --net net_output.bin"
                  << std::endl;
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

int main(int argc, char **argv)
{
    try
    {
        monitor_config config;
        try
        {
            config = parse_arguments(argc, argv);
        }
        catch (std::invalid_argument error)
        {
            std::cerr << error.what() << std::endl;
            return -1;
        }
        const double time_interval = 1000.0 / config.sampling_frequency;

        signal(SIGINT, signal_handler);
        std::vector<std::future<void>> tasks;
        if (config.enable_cpu)
        {
            tasks.emplace_back(std::async(std::launch::async,
                                          [&]() { rt_monitor::cpu::start(time_interval, config.output_files["cpu"], running); }));
        }
        if (config.enable_cpufreq)
        {
            tasks.emplace_back(std::async(
                std::launch::async, [&]() { rt_monitor::cpufreq::start(time_interval, config.output_files["cpu-freq"], running); }));
        }
        if (config.enable_disk)
        {
            tasks.emplace_back(std::async(std::launch::async,
                                          [&]() { rt_monitor::disk::start(time_interval, config.output_files["disk"], running); }));
        }
        if (config.enable_mem)
        {
            tasks.emplace_back(std::async(std::launch::async,
                                          [&]() { rt_monitor::mem::start(time_interval, config.output_files["mem"], running); }));
        }
        if (config.enable_net)
        {
            tasks.emplace_back(std::async(std::launch::async,
                                          [&]() { rt_monitor::net::start(time_interval, config.output_files["net"], running); }));
        }

        for (auto &task : tasks)
        {
            task.wait();
        }
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
