#include <Point.h>
#include <filesystem>
#include <scn/scan.h>
#include <thread>

#include "cpufreq_monitor.h"
#include "db_stream.hpp"
#include "file_stream.hpp"
#include "monitor_io.h"
#include "pause_manager.h"
#include "thread_safe_queue.hpp"

namespace rt_monitor::cpufreq
{
struct data_sample
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    uint32_t cpuid;
    uint32_t frequency;
};
} // namespace rt_monitor::cpufreq

namespace rt_monitor
{
template <> db_stream &db_stream::operator<< <cpufreq::data_sample>(cpufreq::data_sample sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    auto point = influxdb::Point{"cpu_freq"}
                     .addTag("hostname", hostname)
                     .addTag("cpu", "cpu" + std::to_string(sample.cpuid))
                     .addField("value", static_cast<long long int>(sample.frequency))
                     .setTimestamp(sample.timestamp);
    
    spdlog::trace("Buffering cpufreq sample for core {} to InfluxDB", sample.cpuid);

    try
    {
        this->db_ptr_->write(std::move(point));
    }
    catch (const std::runtime_error &e)
    {
        spdlog::error(std::string{"Error while pushing a cpufreq sample: "} + e.what());
    }

    return *this;
}

template <> file_stream &file_stream::operator<< <cpufreq::data_sample>(cpufreq::data_sample sample)
{
    io::write_binary(this->file_, sample.timestamp.time_since_epoch().count());
    io::write_binary(this->file_, sample.cpuid);
    io::write_binary(this->file_, sample.frequency);
    return *this;
}
} // namespace rt_monitor

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
    else
    {
        spdlog::error("Failed to fetch CPU min frequency. Please check the availability and access permissions of "
                      "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq");
    }

    if (max_freq_file.is_open())
    {
        max_freq_file >> max_freq;
    }
    else
    {
        spdlog::error("Failed to fetch CPU max frequency. Please check the availability and access permissions of "
                      "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq");
    }

    return {min_freq, max_freq};
}

void read_cpu_frequency_sample(const std::vector<std::string> &cpu_freq_paths, std::ostream &file)
{
    spdlog::trace("reading a CPU frequency monitoring sample");
    const auto now = std::chrono::system_clock::now();
    const auto duration = now.time_since_epoch();
    const auto timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();

    for (uint32_t i = 0; i < cpu_freq_paths.size(); ++i)
    {
        const auto &path = cpu_freq_paths[i];
        spdlog::trace(path);
        std::ifstream freq_file(path);

        std::string line;
        std::getline(freq_file, line);
        spdlog::trace(line);
        const auto result = scn::scan<uint32_t>(line, "{}");
        if (!result)
        {
            spdlog::debug("Invalid CPU frequency sample.");
            continue;
        }

        const auto [frequency] = result->values();
        io::write_binary(file, timestamp);
        io::write_binary(file, i);
        io::write_binary(file, frequency);
    }
}

void read_cpu_frequency_samples(const std::vector<std::string> &cpu_freq_paths,
                                std::vector<data_sample> &cpufreq_samples_map)
{
    spdlog::trace("reading a CPU frequency monitoring sample");
    const auto now = std::chrono::system_clock::now();

    for (uint32_t i = 0; i < cpu_freq_paths.size(); ++i)
    {
        const auto &path = cpu_freq_paths[i];
        spdlog::trace(path);
        std::ifstream freq_file(path);

        std::string line;
        std::getline(freq_file, line);
        spdlog::trace(line);
        const auto result = scn::scan<uint32_t>(line, "{}");
        if (!result)
        {
            spdlog::debug("Invalid CPU frequency sample.");
            continue;
        }

        const auto [frequency] = result->values();
        data_sample sample{now, i, frequency};
        cpufreq_samples_map[i] = sample;
    }
}

void cpufreq_producer(double time_interval, 
                      const std::vector<std::string>& cpu_freq_paths,
                      ThreadSafeQueue<std::vector<data_sample>>& queue)
{
    bool sampling_warning_provided = false;
    while (!pause_manager::stopped())
    {
        pause_manager::wait_if_paused();

        const auto begin = std::chrono::high_resolution_clock::now();
        
        std::vector<data_sample> samples;
        samples.resize(cpu_freq_paths.size());
        read_cpu_frequency_samples(cpu_freq_paths, samples);
        queue.push(std::move(samples));

        const auto end = std::chrono::high_resolution_clock::now();
        const auto sampling_time = std::chrono::duration_cast<std::chrono::milliseconds>(end - begin).count();
        auto time_to_wait = time_interval - sampling_time;
        if (time_to_wait < 0.)
        {
            if (!sampling_warning_provided)
            {
                spdlog::warn("The sampling period of {} ms might be too low for CPU frequency monitoring. The last "
                             "sampling time "
                             "was {} ms. Samples might be missed. Consider reducing the sampling frequency.",
                             static_cast<int>(time_interval), sampling_time);
                sampling_warning_provided = true;
            }
            time_to_wait = 0.;
        }

        pause_manager::sleep_for(std::chrono::milliseconds(static_cast<int64_t>(time_to_wait)));
    }
    queue.stop();
    spdlog::trace("cpufreq producer stopped");
}

template <typename stream_type> void start_sampling(double time_interval, stream_type &&stream)
{
    const auto cpu_freq_paths = get_online_cpu_scaling_freq_paths();
    if (cpu_freq_paths.empty())
    {
        spdlog::error("No CPU frequency file available, stopping CPU frequency monitoring.");
        return;
    }

    ThreadSafeQueue<std::vector<data_sample>> queue;
    std::thread producer_thread(cpufreq_producer, time_interval, std::cref(cpu_freq_paths), std::ref(queue));

    std::vector<data_sample> samples;
    while (queue.pop(samples))
    {
        if (pause_manager::stopped()) break;
        for (const auto sample : samples)
        {
            stream << sample;
        }
        spdlog::debug("Buffered {} cpufreq samples for InfluxDB", samples.size());
    }
    producer_thread.join();
    spdlog::trace("CPU frequency monitoring stopped");
}

template void start_sampling<db_stream>(double time_interval, db_stream &&stream);
template void start_sampling<file_stream>(double time_interval, file_stream &&stream);
} // namespace rt_monitor::cpufreq
