#include <future>

#include "cpu_monitor.h"
#include "cpufreq_monitor.h"
#include "db_stream.hpp"
#include "file_stream.hpp"
#include "disk_monitor.h"
#include "mem_monitor.h"
#include "net_monitor.h"
#include "ib_monitor.h"
#include "variable_monitor.h"
#include "pause_manager.h"
#include "spdlog/common.h"
#include <unistd.h>
#include <fcntl.h>
#include <sys/select.h>
#include <signal.h>
#include <curl/curl.h>

namespace rt_monitor
{
int signal_pipe[2];

void signal_handler(const int signal)
{
    if (signal == SIGINT || signal == SIGUSR1 || signal == SIGUSR2)
    {
        uint8_t sig_byte = static_cast<uint8_t>(signal);
        [[maybe_unused]] auto ignored = write(signal_pipe[1], &sig_byte, sizeof(sig_byte));
    }
}

struct monitor_config
{
    bool enable_cpu = false;
    bool enable_cpufreq = false;
    bool enable_disk = false;
    bool enable_mem = false;
    bool enable_net = false;
    bool enable_ib = false;
    double sampling_frequency = 0.0;
    std::string grafana_address = "";
    int batch_size = 1;
    spdlog::level::level_enum log_level = spdlog::level::err;
    std::unordered_map<std::string, std::string> output_files;
};

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
        spdlog::error("Usage: {} --sampling-frequency <Hz> [--cpu <cpu_output_file_path>] [--cpu-freq "
                      "<cpu_freq_output_file_path>] "
                      "[--disk <disk_output_file_path>] [--mem <mem_output_file_path>] [--net <net_output_file_path>] "
                      "[--ib <ib_output_file_path>] "
                      "[--log-level <trace/debug/info/warn/error/critical/off] [--grafana <db address>]",
                      argv[0]);
        exit(1);
    }

    monitor_config config;
    for (int i = 1; i < argc; ++i)
    {
        std::string arg = argv[i];
        if (arg == "--sampling-frequency")
        {
            if (i + 1 >= argc) throw std::invalid_argument("Missing value for --sampling-frequency");
            config.sampling_frequency = std::stod(argv[++i]);
            if (config.sampling_frequency <= 0) throw std::invalid_argument("Sampling frequency must be greater than 0");
        }
        else if (arg == "--cpu")
        {
            config.enable_cpu = true;
            if (i + 1 < argc && argv[i + 1][0] != '-')
            {
                config.output_files["cpu"] = argv[++i];
            }
        }
        else if (arg == "--cpu-freq")
        {
            config.enable_cpufreq = true;
            if (i + 1 < argc && argv[i + 1][0] != '-')
            {
                config.output_files["cpu-freq"] = argv[++i];
            }
        }
        else if (arg == "--disk")
        {
            config.enable_disk = true;
            if (i + 1 < argc && argv[i + 1][0] != '-')
            {
                config.output_files["disk"] = argv[++i];
            }
        }
        else if (arg == "--mem")
        {
            config.enable_mem = true;
            if (i + 1 < argc && argv[i + 1][0] != '-')
            {
                config.output_files["mem"] = argv[++i];
            }
        }
        else if (arg == "--net")
        {
            config.enable_net = true;
            if (i + 1 < argc && argv[i + 1][0] != '-')
            {
                config.output_files["net"] = argv[++i];
            }
        }
        else if (arg == "--ib")
        {
            config.enable_ib = true;
            if (i + 1 < argc && argv[i + 1][0] != '-')
            {
                config.output_files["ib"] = argv[++i];
            }
        }
        else if (arg == "--log-level")
        {
            if (i + 1 >= argc) throw std::invalid_argument("Missing value for --log-level");
            config.log_level = parse_log_level(argv[++i]);
        }
        else if (arg == "--grafana")
        {
            if (i + 1 >= argc) throw std::invalid_argument("Missing value for --grafana");
            config.grafana_address = argv[++i];
        }
        else if (arg == "--batch-size")
        {
            if (i + 1 >= argc) throw std::invalid_argument("Missing value for --batch-size");
            config.batch_size = std::stoi(argv[++i]);
            if (config.batch_size <= 0) throw std::invalid_argument("Batch size must be greater than 0");
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

int get_batch_size(const std::string& metric, int base_batch_size) {
    // High cardinality metrics (per core)
    if (metric == "cpu" || metric == "cpufreq") {
        return base_batch_size;
    }
    
    // Low cardinality metrics (per system or per few devices)
    // We scale down the batch size for these metrics so they flush at a reasonable frequency
    // relative to the high-cardinality metrics.
    
    if (metric == "mem" || metric == "disk" || metric == "ib") {
        int size = base_batch_size / 100;
        return size < 10 ? 10 : size;
    }
    
    if (metric == "net") {
        int size = base_batch_size / 10;
        return size < 10 ? 10 : size;
    }
    
    return base_batch_size;
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

        curl_global_init(CURL_GLOBAL_ALL);

        if (pipe(signal_pipe) == -1)
        {
            spdlog::error("Failed to create signal pipe");
            return -1;
        }
        fcntl(signal_pipe[0], F_SETFL, O_NONBLOCK);
        fcntl(signal_pipe[1], F_SETFL, O_NONBLOCK);

        signal(SIGINT, signal_handler);
        signal(SIGUSR1, signal_handler);
        signal(SIGUSR2, signal_handler);

        std::string db_address = config.grafana_address;
        bool use_db = !db_address.empty();

        if (!use_db)
        {
            if (config.enable_cpu && config.output_files["cpu"].empty())
            {
                spdlog::error("CPU output file path is required when not using Grafana");
                return -1;
            }
            if (config.enable_cpufreq && config.output_files["cpu-freq"].empty())
            {
                spdlog::error("CPU frequency output file path is required when not using Grafana");
                return -1;
            }
            if (config.enable_disk && config.output_files["disk"].empty())
            {
                spdlog::error("Disk output file path is required when not using Grafana");
                return -1;
            }
            if (config.enable_mem && config.output_files["mem"].empty())
            {
                spdlog::error("Memory output file path is required when not using Grafana");
                return -1;
            }
            if (config.enable_net && config.output_files["net"].empty())
            {
                spdlog::error("Network output file path is required when not using Grafana");
                return -1;
            }
            if (config.enable_ib && config.output_files["ib"].empty())
            {
                spdlog::error("InfiniBand output file path is required when not using Grafana");
                return -1;
            }
        }

        std::vector<std::future<void>> tasks;

        if (use_db)
        {
            tasks.emplace_back(std::async(std::launch::async, [db_address]() {
                db_stream stream(db_address);
                rt_monitor::variable::start_sampling(std::move(stream));
            }));
        }

        if (config.enable_cpu)
        {
            if (!use_db)
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() {
                    file_stream stream(config.output_files["cpu"]);
                    rt_monitor::cpu::start_sampling(time_interval, std::move(stream));
                }));
            }
            else
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() mutable {
                    db_stream stream(db_address);
                    stream.set_buffer_size(get_batch_size("cpu", config.batch_size));
                    rt_monitor::cpu::start_sampling(time_interval, std::move(stream));
                }));
            }
        }
        if (config.enable_cpufreq)
        {
            if (!use_db)
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() {
                    file_stream stream(config.output_files["cpu-freq"]);
                    rt_monitor::cpufreq::start_sampling(time_interval, std::move(stream));
                }));
            }
            else
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() mutable {
                    db_stream stream(db_address);
                    stream.set_buffer_size(get_batch_size("cpufreq", config.batch_size));
                    rt_monitor::cpufreq::start_sampling(time_interval, std::move(stream));
                }));
            }
        }
        if (config.enable_disk)
        {
            if (!use_db)
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() {
                    file_stream stream(config.output_files["disk"]);
                    rt_monitor::disk::start_sampling(time_interval, std::move(stream));
                }));
            }
            else
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() mutable {
                    db_stream stream(db_address);
                    stream.set_buffer_size(get_batch_size("disk", config.batch_size));
                    rt_monitor::disk::start_sampling(time_interval, std::move(stream));
                }));
            }
        }
        if (config.enable_mem)
        {
            if (!use_db)
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() {
                    file_stream stream(config.output_files["mem"]);
                    rt_monitor::mem::start_sampling(time_interval, std::move(stream));
                }));
            }
            else
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() mutable {
                    db_stream stream(db_address);
                    stream.set_buffer_size(get_batch_size("mem", config.batch_size));
                    rt_monitor::mem::start_sampling(time_interval, std::move(stream));
                }));
            }
        }
        if (config.enable_net)
        {
            if (!use_db)
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() {
                    file_stream stream(config.output_files["net"]);
                    rt_monitor::net::start_sampling(time_interval, std::move(stream));
                }));
            }
            else
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() mutable {
                    db_stream stream(db_address);
                    stream.set_buffer_size(get_batch_size("net", config.batch_size));
                    rt_monitor::net::start_sampling(time_interval, std::move(stream));
                }));
            }
        }
        if (config.enable_ib)
        {
            if (!use_db)
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() {
                    file_stream stream(config.output_files["ib"]);
                    rt_monitor::ib::start_sampling(time_interval, std::move(stream));
                }));
            }
            else
            {
                tasks.emplace_back(std::async(std::launch::async, [&]() mutable {
                    db_stream stream(db_address);
                    stream.set_buffer_size(get_batch_size("ib", config.batch_size));
                    rt_monitor::ib::start_sampling(time_interval, std::move(stream));
                }));
            }
        }

        pause_manager::resume();

        fd_set readfds;
        int max_fd = signal_pipe[0] + 1;
        bool running = true;

        while (running)
        {
            FD_ZERO(&readfds);
            FD_SET(signal_pipe[0], &readfds);

            int activity = select(max_fd, &readfds, nullptr, nullptr, nullptr);

            if (activity < 0 && errno != EINTR)
            {
                spdlog::error("Select error");
                break;
            }

            if (activity > 0 && FD_ISSET(signal_pipe[0], &readfds))
            {
                uint8_t sig_byte;
                while (read(signal_pipe[0], &sig_byte, sizeof(sig_byte)) > 0)
                {
                    int sig = static_cast<int>(sig_byte);
                    if (sig == SIGINT)
                    {
                        spdlog::info("Received SIGINT, stopping...");
                        pause_manager::stop();
                        running = false;
                    }
                    else if (sig == SIGUSR1)
                    {
                        spdlog::info("Received SIGUSR1, pausing...");
                        pause_manager::pause();
                    }
                    else if (sig == SIGUSR2)
                    {
                        spdlog::info("Received SIGUSR2, resuming...");
                        pause_manager::resume();
                    }
                }
            }
        }

        auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
        spdlog::info("Waiting for worker threads to finish...");
        for (auto &task : tasks)
        {
            if (task.wait_until(deadline) == std::future_status::timeout)
            {
                spdlog::warn("Timeout reached while waiting for tasks to stop. Forcing exit.");
                exit(0);
            }
        }
        spdlog::info("All tasks finished. Exiting.");
    }
    catch (const std::exception &e)
    {
        spdlog::error(e.what());
        curl_global_cleanup();
        return 1;
    }

    curl_global_cleanup();
    return 0;
}
