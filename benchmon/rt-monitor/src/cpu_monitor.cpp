#include "cpu_monitor.h"
#include "db_stream.hpp"
#include "file_stream.hpp"
#include "monitor_io.h"
#include "pause_manager.h"
#include "thread_safe_queue.hpp"
#include <thread>
#include <fcntl.h>
#include <unistd.h>

namespace rt_monitor
{
namespace cpu
{
struct data_sample
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    uint32_t cpuid;
    uint64_t user_value;
    uint64_t nice_value;
    uint64_t system_value;
    uint64_t idle_value;
    uint64_t iowait_value;
    uint64_t irq_value;
    uint64_t softirq_value;
    uint64_t steal_value;
    uint64_t guest_value;
    uint64_t guestnice_value;

    data_sample operator-=(const data_sample &sample)
    {
        assert(sample.cpuid == cpuid);
        user_value -= sample.user_value;
        nice_value -= sample.nice_value;
        system_value -= sample.system_value;
        idle_value -= sample.idle_value;
        iowait_value -= sample.iowait_value;
        irq_value -= sample.irq_value;
        softirq_value -= sample.softirq_value;
        steal_value -= sample.steal_value;
        guest_value -= sample.guest_value;
        guestnice_value -= sample.guestnice_value;
        return *this;
    }

    data_sample operator-(const data_sample &sample) const
    {
        data_sample result = *this;
        result -= sample;
        return result;
    }
};
} // namespace cpu

template <> db_stream &db_stream::operator<< <cpu::data_sample>(cpu::data_sample sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();

    std::stringstream ss;
    if (sample.cpuid == std::numeric_limits<uint32_t>::max()) {
        ss << "cpu_total";
    } else {
        ss << "cpu_core,cpu=cpu" << sample.cpuid;
    }

    ss << ",hostname=" << hostname << " ";
    ss << "user=" << sample.user_value << "i,"
       << "nice=" << sample.nice_value << "i,"
       << "system=" << sample.system_value << "i,"
       << "idle=" << sample.idle_value << "i,"
       << "iowait=" << sample.iowait_value << "i,"
       << "irq=" << sample.irq_value << "i,"
       << "softirq=" << sample.softirq_value << "i,"
       << "steal=" << sample.steal_value << "i,"
       << "guest=" << sample.guest_value << "i,"
       << "guest_nice=" << sample.guestnice_value << "i";
    
    ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();

    this->write_line(ss.str());
    
    spdlog::trace("Buffering CPU sample for core {} to InfluxDB", sample.cpuid);

    return *this;
}

template <> db_stream &db_stream::operator<< <std::unordered_map<uint32_t, cpu::data_sample>>(std::unordered_map<uint32_t, cpu::data_sample> samples)
{
    if (samples.empty()) return *this;
    static const std::string hostname = rt_monitor::io::get_hostname();
    
    // Use the timestamp from the first sample for all samples in this batch
    auto timestamp_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(samples.begin()->second.timestamp.time_since_epoch()).count();
    std::string timestamp_str = std::to_string(timestamp_ns);

    for (const auto& [cpuid, sample] : samples) {
        std::string line;
        line.reserve(256); // Pre-allocate to avoid reallocations

        if (cpuid == std::numeric_limits<uint32_t>::max()) {
            line += "cpu_total";
        } else {
            line += "cpu_core,cpu=cpu";
            line += std::to_string(cpuid);
        }

        line += ",hostname=";
        line += hostname;
        line += " ";
        
        line += "user="; line += std::to_string(sample.user_value); line += "i,";
        line += "nice="; line += std::to_string(sample.nice_value); line += "i,";
        line += "system="; line += std::to_string(sample.system_value); line += "i,";
        line += "idle="; line += std::to_string(sample.idle_value); line += "i,";
        line += "iowait="; line += std::to_string(sample.iowait_value); line += "i,";
        line += "irq="; line += std::to_string(sample.irq_value); line += "i,";
        line += "softirq="; line += std::to_string(sample.softirq_value); line += "i,";
        line += "steal="; line += std::to_string(sample.steal_value); line += "i,";
        line += "guest="; line += std::to_string(sample.guest_value); line += "i,";
        line += "guest_nice="; line += std::to_string(sample.guestnice_value); line += "i ";
        
        line += timestamp_str;

        this->write_line(line);
    }
    
    spdlog::debug("Buffered {} CPU samples for InfluxDB", samples.size());
    return *this;
}

template <> file_stream &file_stream::operator<< <cpu::data_sample>(cpu::data_sample sample)
{
    io::write_binary(this->file_, sample.timestamp);
    io::write_binary(this->file_, sample.cpuid);
    io::write_binary(this->file_, sample.user_value);
    io::write_binary(this->file_, sample.nice_value);
    io::write_binary(this->file_, sample.system_value);
    io::write_binary(this->file_, sample.idle_value);
    io::write_binary(this->file_, sample.iowait_value);
    io::write_binary(this->file_, sample.irq_value);
    io::write_binary(this->file_, sample.softirq_value);
    io::write_binary(this->file_, sample.steal_value);
    io::write_binary(this->file_, sample.guest_value);
    io::write_binary(this->file_, sample.guestnice_value);
    return *this;
}

template <> file_stream &file_stream::operator<< <std::unordered_map<uint32_t, cpu::data_sample>>(std::unordered_map<uint32_t, cpu::data_sample> samples)
{
    for (const auto& [cpuid, sample] : samples) {
        *this << sample;
    }
    return *this;
}

namespace cpu
{
void read_cpu_samples(int fd, std::unordered_map<uint32_t, data_sample> &cpu_samples_map)
{
    spdlog::trace("reading a CPU monitoring sample");
    const auto now = std::chrono::system_clock::now();
    
    char buffer[65536]; // 64KB should be enough for /proc/stat
    // Use pread to read from offset 0 without changing the file offset
    ssize_t bytes_read = pread(fd, buffer, sizeof(buffer) - 1, 0);
    if (bytes_read <= 0) return;
    buffer[bytes_read] = '\0';

    std::string content(buffer);
    std::istringstream iss(content);
    std::string line;

    while (std::getline(iss, line))
    {
        if (!line.starts_with("cpu"))
            break;

        char cpuid_str[32];
        uint64_t user_value, nice_value, system_value, idle_value, iowait_value, irq_value, softirq_value, steal_value, guest_value, guestnice_value;
        
        int ret = sscanf(line.c_str(), "%s %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu", 
            cpuid_str, &user_value, &nice_value, &system_value, &idle_value, &iowait_value, &irq_value, &softirq_value, &steal_value, &guest_value, &guestnice_value);

        if (ret < 11)
            continue;

        std::string cpuid_value(cpuid_str);
        const auto cpuid = io::cpuid_str_to_uint(cpuid_value);

        data_sample sample{now,          cpuid,     user_value,    nice_value,  system_value, idle_value,
                           iowait_value, irq_value, softirq_value, steal_value, guest_value,  guestnice_value};
        cpu_samples_map[cpuid] = sample;
    }
}

void cpu_producer(double time_interval, ThreadSafeQueue<std::unordered_map<uint32_t, data_sample>>& queue)
{
    int fd = open("/proc/stat", O_RDONLY);
    if (fd < 0) {
        spdlog::error("Failed to open /proc/stat");
        queue.stop();
        return;
    }

    bool sampling_warning_provided = false;
    while (!pause_manager::stopped())
    {
        pause_manager::wait_if_paused();

        const auto begin = std::chrono::high_resolution_clock::now();
        
        std::unordered_map<uint32_t, data_sample> samples;
        read_cpu_samples(fd, samples);
        spdlog::debug("Collected {} CPU samples", samples.size());
        queue.push(std::move(samples));

        const auto end = std::chrono::high_resolution_clock::now();
        const auto sampling_time = std::chrono::duration_cast<std::chrono::milliseconds>(end - begin).count();
        auto time_to_wait = time_interval - sampling_time;
        if (time_to_wait < 0.)
        {
            if (!sampling_warning_provided)
            {
                spdlog::warn("The sampling period of {} ms might be too low for CPU monitoring. The last sampling time "
                             "was {} ms. Samples might be missed. Consider reducing the sampling frequency.",
                             static_cast<int>(time_interval), sampling_time);
                sampling_warning_provided = true;
            }
            time_to_wait = 0.;
        }
        pause_manager::sleep_for(std::chrono::milliseconds(static_cast<int64_t>(time_to_wait)));
    }
    close(fd);
    queue.stop();
    spdlog::trace("CPU producer stopped");
}

template <typename stream_type> void start_sampling(double time_interval, stream_type &&stream);

template <> void start_sampling(const double time_interval, db_stream &&stream)
{
    ThreadSafeQueue<std::unordered_map<uint32_t, data_sample>> queue;
    std::thread producer_thread(cpu_producer, time_interval, std::ref(queue));

    std::unordered_map<uint32_t, data_sample> current_sample_set;
    while (queue.pop(current_sample_set))
    {
        if (pause_manager::stopped()) break;
        stream << current_sample_set;
    }
    
    producer_thread.join();
    spdlog::trace("CPU monitoring stopped");
}

template <> void start_sampling(const double time_interval, file_stream &&stream)
{
    ThreadSafeQueue<std::unordered_map<uint32_t, data_sample>> queue;
    std::thread producer_thread(cpu_producer, time_interval, std::ref(queue));

    std::unordered_map<uint32_t, data_sample> samples_set;
    while (queue.pop(samples_set))
    {
        if (pause_manager::stopped()) break;
        for (const auto [index, current_sample] : samples_set)
        {
            stream << current_sample;
        }
    }
    producer_thread.join();
    spdlog::trace("CPU monitoring stopped");
}
} // namespace cpu
} // namespace rt_monitor