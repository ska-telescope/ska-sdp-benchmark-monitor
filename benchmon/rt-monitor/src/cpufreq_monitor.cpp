#include <filesystem>
#include <thread>
#include <fcntl.h>
#include <unistd.h>
#include <charconv>
#include <vector>

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

struct CpuSource {
    uint32_t cpuid;
    int fd;
};

} // namespace rt_monitor::cpufreq

namespace rt_monitor
{
template <> db_stream &db_stream::operator<< <cpufreq::data_sample>(cpufreq::data_sample sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    
    std::stringstream ss;
    ss << "cpu_freq,hostname=" << hostname << ",cpu=cpu" << sample.cpuid << " ";
    ss << "value=" << sample.frequency << "i";
    ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();

    this->write_line(ss.str());
    
    spdlog::trace("Buffering cpufreq sample for core {} to InfluxDB", sample.cpuid);

    return *this;
}

template <> db_stream &db_stream::operator<< <std::vector<cpufreq::data_sample>>(std::vector<cpufreq::data_sample> samples)
{
    if (samples.empty()) return *this;
    static const std::string hostname = rt_monitor::io::get_hostname();
    
    // Pre-calculate timestamp string once for the whole batch
    auto timestamp_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(samples[0].timestamp.time_since_epoch()).count();
    std::string timestamp_str = std::to_string(timestamp_ns);

    for (const auto& sample : samples) {
        // Use string concatenation instead of stringstream for performance
        std::string line = "cpu_freq,hostname=";
        line += hostname;
        line += ",cpu=cpu";
        line += std::to_string(sample.cpuid);
        line += " value=";
        line += std::to_string(sample.frequency);
        line += "i ";
        line += timestamp_str;
        
        this->write_line(line);
    }
    
    spdlog::trace("Buffered {} cpufreq samples for InfluxDB", samples.size());
    return *this;
}

template <> file_stream &file_stream::operator<< <cpufreq::data_sample>(cpufreq::data_sample sample)
{
    io::write_binary(this->file_, sample.timestamp.time_since_epoch().count());
    io::write_binary(this->file_, sample.cpuid);
    io::write_binary(this->file_, sample.frequency);
    return *this;
}

template <> file_stream &file_stream::operator<< <std::vector<cpufreq::data_sample>>(std::vector<cpufreq::data_sample> samples)
{
    for (const auto& sample : samples) {
        *this << sample;
    }
    return *this;
}
} // namespace rt_monitor

namespace rt_monitor::cpufreq
{
std::vector<CpuSource> get_cpu_freq_sources()
{
    std::vector<CpuSource> sources;
    std::vector<std::pair<int, std::string>> indexed_paths;

    auto cpu_path_iterator = std::filesystem::directory_iterator("/sys/devices/system/cpu");
    for (const auto &entry : cpu_path_iterator)
    {
        if (entry.is_directory() && entry.path().filename().string().starts_with("cpu"))
        {
            std::string online_path = entry.path().string() + "/online";
            bool is_online = true; // cpu0 often doesn't have 'online' file and is always online
            
            if (std::filesystem::exists(online_path))
            {
                std::ifstream online_file(online_path);
                int online_status;
                online_file >> online_status;
                if (online_status != 1) {
                    is_online = false;
                }
            }

            if (is_online)
            {
                std::string scaling_freq_path = entry.path().string() + "/cpufreq/scaling_cur_freq";
                if (std::filesystem::exists(scaling_freq_path))
                {
                    std::string cpu_dir_name = entry.path().filename().string();
                    // Handle "cpu0", "cpu1" etc.
                    try {
                        int cpu_index = std::stoi(cpu_dir_name.substr(3));
                        indexed_paths.emplace_back(cpu_index, scaling_freq_path);
                    } catch (...) {
                        continue;
                    }
                }
            }
        }
    }

    std::sort(indexed_paths.begin(), indexed_paths.end());
    
    for (const auto &[index, path] : indexed_paths)
    {
        int fd = open(path.c_str(), O_RDONLY);
        if (fd >= 0) {
            sources.push_back({static_cast<uint32_t>(index), fd});
        } else {
            spdlog::warn("Failed to open CPU frequency file: {}", path);
        }
    }
    return sources;
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

void read_cpu_frequency_samples(const std::vector<CpuSource> &sources,
                                std::vector<data_sample> &samples)
{
    spdlog::trace("reading a CPU frequency monitoring sample");
    const auto now = std::chrono::system_clock::now();
    char buffer[32];

    samples.clear();
    samples.reserve(sources.size());

    for (const auto &source : sources)
    {
        // Use pread to read from offset 0 without changing the file offset
        // This avoids a separate lseek syscall for each file
        ssize_t bytes_read = pread(source.fd, buffer, sizeof(buffer) - 1, 0);
        if (bytes_read > 0) {
            buffer[bytes_read] = '\0';
            uint32_t frequency = 0;
            auto [ptr, ec] = std::from_chars(buffer, buffer + bytes_read, frequency);
            if (ec == std::errc()) {
                samples.push_back({now, source.cpuid, frequency});
            }
        }
    }
}

void cpufreq_producer(double time_interval, 
                      const std::vector<CpuSource>& sources,
                      ThreadSafeQueue<std::vector<data_sample>>& queue)
{
    bool sampling_warning_provided = false;
    while (!pause_manager::stopped())
    {
        pause_manager::wait_if_paused();

        const auto begin = std::chrono::high_resolution_clock::now();
        
        std::vector<data_sample> samples;
        read_cpu_frequency_samples(sources, samples);
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
    const auto sources = get_cpu_freq_sources();
    if (sources.empty())
    {
        spdlog::error("No CPU frequency file available, stopping CPU frequency monitoring.");
        return;
    }

    ThreadSafeQueue<std::vector<data_sample>> queue;
    std::thread producer_thread(cpufreq_producer, time_interval, std::cref(sources), std::ref(queue));

    std::vector<data_sample> samples;
    while (queue.pop(samples))
    {
        if (pause_manager::stopped()) break;
        stream << samples;
    }
    producer_thread.join();
    
    // Cleanup FDs
    for(const auto& source : sources) {
        close(source.fd);
    }
    
    spdlog::trace("CPU frequency monitoring stopped");
}

template void start_sampling<db_stream>(double time_interval, db_stream &&stream);
template void start_sampling<file_stream>(double time_interval, file_stream &&stream);
} // namespace rt_monitor::cpufreq
