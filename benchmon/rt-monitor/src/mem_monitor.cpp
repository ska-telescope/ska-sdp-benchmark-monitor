#include "db_stream.hpp"
#include "file_stream.hpp"
#include "mem_monitor.h"
#include "monitor_io.h"
#include "pause_manager.h"
#include "thread_safe_queue.hpp"
#include <thread>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>

namespace rt_monitor::mem
{
struct data_sample
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    std::unordered_map<std::string, uint64_t> values_map;
};
} // namespace rt_monitor::mem

namespace rt_monitor
{
template <> db_stream &db_stream::operator<< <mem::data_sample>(mem::data_sample sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    std::stringstream ss;
    ss << "memory,hostname=" << hostname << " ";
    
    bool first = true;
    for (const auto [label, value] : sample.values_map)
    {
        if (!first) ss << ",";
        std::string lower_label = label;
        std::transform(lower_label.begin(), lower_label.end(), lower_label.begin(),
                       [](unsigned char c){ return std::tolower(c); });
        ss << lower_label << "=" << value << "i";
        first = false;
    }
    ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
    
    this->write_line(ss.str());
    
    spdlog::debug("Sending memory sample to InfluxDB");

    return *this;
}

template <> file_stream &file_stream::operator<< <mem::data_sample>(mem::data_sample sample)
{
    io::write_binary(this->file_, static_cast<uint64_t>(sample.timestamp.time_since_epoch().count()));

    for (const auto [label, value] : sample.values_map)
    {
        io::write_binary(this->file_, value);
    }
    return *this;
}
} // namespace rt_monitor

namespace rt_monitor::mem
{
constexpr size_t n_fields = 55;
constexpr std::array<bool, n_fields> enabled{
    true,  true,  false, true,  true,  true,  false, false, false, false, false, false, false, false,
    true,  true,  false, false, false, false, false, false, false, false, true,  false, false, false,
    false, false, false, false, false, false, false, false, false, false, false, false, false, false,
    false, false, false, false, false, false, false, false, false, false, false, false, false};
constexpr std::array<std::string_view, n_fields> field_names{
    "MemTotal",      "MemFree",         "MemAvailable",   "Buffers",        "Cached",
    "SwapCached",    "Active",          "Inactive",       "Active(anon",    "Inactive(anon",
    "Active(file",   "Inactive(file",   "Unevictable",    "Mlocked",        "SwapTotal",
    "SwapFree",      "Zswap",           "Zswapped",       "Dirty",          "Writeback",
    "AnonPages",     "Mapped",          "Shmem",          "KReclaimable",   "Slab",
    "SReclaimable",  "SUnreclaim",      "KernelStack",    "PageTables",     "SecPageTables",
    "NFS_Unstable",  "Bounce",          "WritebackTmp",   "CommitLimit",    "Committed_AS",
    "VmallocTotal",  "VmallocUsed",     "VmallocChunk",   "Percpu",         "HardwareCorrupted",
    "AnonHugePages", "ShmemHugePages",  "ShmemPmdMapped", "FileHugePages",  "FilePmdMapped",
    "Unaccepted",    "HugePages_Total", "HugePages_Free", "HugePages_Rsvd", "HugePages_Surp",
    "Hugepagesize",  "Hugetlb",         "DirectMap4k",    "DirectMap2M",    "DirectMap1G"};

data_sample read_mem_sample(int fd)
{
    spdlog::trace("reading a memory monitoring sample");
    const auto now = std::chrono::system_clock::now();

    if (lseek(fd, 0, SEEK_SET) == -1) return {};

    char buffer[8192]; // 8KB should be enough for /proc/meminfo
    ssize_t bytes_read = read(fd, buffer, sizeof(buffer) - 1);
    if (bytes_read <= 0) return {};
    buffer[bytes_read] = '\0';

    data_sample sample;
    sample.timestamp = now;

    std::string content(buffer);
    std::istringstream iss(content);
    std::string line;

    int i = 0;
    while (std::getline(iss, line) && i < 55)
    {
        if (enabled[i])
        {
            const auto value_start = line.find_first_of("0123456789");
            const auto value_end = line.find_last_of("0123456789") + 1;
            uint64_t value = 0;
            if (value_start != std::string::npos && value_end != std::string::npos)
            {
                try {
                    value = std::stoull(line.substr(value_start, value_end - value_start));
                } catch (...) {
                    value = 0;
                }
            }
            sample.values_map[std::string(field_names[i])] = value;
        }
        ++i;
    }
    return sample;
}

void mem_producer(double time_interval, ThreadSafeQueue<data_sample>& queue)
{
    int fd = open("/proc/meminfo", O_RDONLY);
    if (fd < 0) {
        spdlog::error("Failed to open /proc/meminfo");
        queue.stop();
        return;
    }

    bool sampling_warning_provided = false;
    while (!pause_manager::stopped())
    {
        pause_manager::wait_if_paused();

        const auto begin = std::chrono::high_resolution_clock::now();
        auto sample = read_mem_sample(fd);
        spdlog::debug("Collected memory sample");
        queue.push(std::move(sample));
        const auto end = std::chrono::high_resolution_clock::now();
        
        const auto sampling_time = std::chrono::duration_cast<std::chrono::milliseconds>(end - begin).count();
        auto time_to_wait = time_interval - sampling_time;
        if (time_to_wait < 0.)
        {
            if (!sampling_warning_provided)
            {
                spdlog::warn(
                    "The sampling period of {} ms might be too low for memory monitoring. The last sampling time "
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
    spdlog::trace("memory producer stopped");
}

template <typename stream_type> void start_sampling(double time_interval, stream_type &&stream)
{
    ThreadSafeQueue<data_sample> queue;
    std::thread producer_thread(mem_producer, time_interval, std::ref(queue));

    data_sample sample;
    while (queue.pop(sample))
    {
        if (pause_manager::stopped()) break;
        stream << sample;
    }
    producer_thread.join();
    spdlog::trace("memory monitoring stopped");
}

template void start_sampling<db_stream>(double time_interval, db_stream &&stream);
template void start_sampling<file_stream>(double time_interval, file_stream &&stream);
} // namespace rt_monitor::mem
