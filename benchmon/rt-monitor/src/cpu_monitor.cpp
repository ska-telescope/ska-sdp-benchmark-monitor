#include <InfluxDBFactory.h>
#include <scn/scan.h>

#include "Point.h"
#include "cpu_monitor.h"
#include "db_stream.hpp"
#include "file_stream.hpp"
#include "monitor_io.h"
#include "pause_manager.h"
#include "thread_safe_queue.hpp"
#include <thread>

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

    std::string measurement;
    influxdb::Point point{""};

    if (sample.cpuid == std::numeric_limits<uint32_t>::max()) {
        measurement = "cpu_total";
        point = influxdb::Point{measurement};
    } else {
        measurement = "cpu_core";
        point = influxdb::Point{measurement};
        point.addTag("cpu", "cpu" + std::to_string(sample.cpuid));
    }

    point.addTag("hostname", hostname)
         .addField("user", static_cast<long long int>(sample.user_value))
         .addField("nice", static_cast<long long int>(sample.nice_value))
         .addField("system", static_cast<long long int>(sample.system_value))
         .addField("idle", static_cast<long long int>(sample.idle_value))
         .addField("iowait", static_cast<long long int>(sample.iowait_value))
         .addField("irq", static_cast<long long int>(sample.irq_value))
         .addField("softirq", static_cast<long long int>(sample.softirq_value))
         .addField("steal", static_cast<long long int>(sample.steal_value))
         .addField("guest", static_cast<long long int>(sample.guest_value))
         .addField("guest_nice", static_cast<long long int>(sample.guestnice_value))
         .setTimestamp(sample.timestamp);
    
    spdlog::trace("Buffering CPU sample for core {} to InfluxDB", sample.cpuid);

    try
    {
        this->db_ptr_->write(std::move(point));
    }
    catch (const std::runtime_error &e)
    {
        spdlog::error(std::string{"Error while pushing a CPU sample: "} + e.what());
    }

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

namespace cpu
{
void read_cpu_samples(std::unordered_map<uint32_t, data_sample> &cpu_samples_map)
{
    spdlog::trace("reading a CPU monitoring sample");
    const auto now = std::chrono::system_clock::now();
    const auto duration = now.time_since_epoch();
    const uint64_t timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();

    std::ifstream file("/proc/stat");
    std::string line;
    while (std::getline(file, line))
    {
        if (!line.starts_with("cpu"))
            break;

        const auto result = scn::scan<std::string, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
                                      uint64_t, uint64_t, uint64_t>(line, "{} {} {} {} {} {} {} {} {} {} {}");
        if (!result)
            continue;
        const auto [cpuid_value, user_value, nice_value, system_value, idle_value, iowait_value, irq_value,
                    softirq_value, steal_value, guest_value, guestnice_value] = result->values();
        const auto cpuid = io::cpuid_str_to_uint(cpuid_value);

        data_sample sample{now,          cpuid,     user_value,    nice_value,  system_value, idle_value,
                           iowait_value, irq_value, softirq_value, steal_value, guest_value,  guestnice_value};
        cpu_samples_map[cpuid] = sample;
    }
}

void cpu_producer(double time_interval, ThreadSafeQueue<std::unordered_map<uint32_t, data_sample>>& queue)
{
    bool sampling_warning_provided = false;
    while (!pause_manager::stopped())
    {
        pause_manager::wait_if_paused();

        const auto begin = std::chrono::high_resolution_clock::now();
        
        std::unordered_map<uint32_t, data_sample> samples;
        read_cpu_samples(samples);
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
        for (const auto [index, current_sample] : current_sample_set)
        {
            stream << current_sample;
        }
        spdlog::debug("Buffered {} CPU samples for InfluxDB", current_sample_set.size());
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