#include <filesystem>
#include <thread>
#include <fcntl.h>
#include <unistd.h>
#include <charconv>
#include <cstring>
#include <cctype>
#include <cstring>

#include "db_stream.hpp"
#include "file_stream.hpp"
#include "monitor_io.h"
#include "pause_manager.h"
#include "spdlog/common.h"
#include "thread_safe_queue.hpp"

namespace rt_monitor::disk
{
struct block_device_info
{
    std::string name;
    uint32_t block_size;
};

struct data_sample
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    uint32_t major;
    uint32_t minor;
    uint32_t index;
    std::string device;
    uint64_t rd_completed;
    uint64_t rd_merged;
    uint64_t sectors_read;
    uint64_t time_read;
    uint64_t wr_completed;
    uint64_t wr_merged;
    uint64_t sectors_written;
    uint64_t time_write;
    uint64_t io_in_progress;
    uint64_t time_io;
    uint64_t time_weighted_io;
    uint64_t disc_completed;
    uint64_t disc_merged;
    uint64_t sectors_discarded;
    uint64_t time_discard;
    uint64_t flush_requests;
    uint64_t time_flush;

    data_sample &operator-=(const data_sample &sample)
    {
        if (device != sample.device || major != sample.major || minor != sample.minor || index != sample.index)
        {
            throw std::invalid_argument("Cannot subtract samples from different devices");
        }
        rd_completed -= sample.rd_completed;
        rd_merged -= sample.rd_merged;
        sectors_read -= sample.sectors_read;
        time_read -= sample.time_read;
        wr_completed -= sample.wr_completed;
        wr_merged -= sample.wr_merged;
        sectors_written -= sample.sectors_written;
        time_write -= sample.time_write;
        io_in_progress -= sample.io_in_progress;
        time_io -= sample.time_io;
        time_weighted_io -= sample.time_weighted_io;
        disc_completed -= sample.disc_completed;
        disc_merged -= sample.disc_merged;
        sectors_discarded -= sample.sectors_discarded;
        time_discard -= sample.time_discard;
        flush_requests -= sample.flush_requests;
        time_flush -= sample.time_flush;
        return *this;
    }

    data_sample operator-(const data_sample &sample) const
    {
        data_sample result = *this;
        result -= sample;
        return result;
    }
};

struct data_sample_diff
{
    data_sample_diff()
    {
    }

    data_sample_diff(const size_t sector_size, const data_sample &sample)
        : timestamp(sample.timestamp), major(sample.major), minor(sample.minor), device(sample.device),
          rd_completed(sample.rd_completed), sectors_read(sample.sectors_read * sector_size),
          wr_completed(sample.wr_completed), sectors_written(sample.sectors_written * sector_size)
    {
    }

    data_sample_diff &operator+=(const data_sample_diff &other)
    {
        rd_completed += other.rd_completed;
        sectors_read += other.sectors_read;
        wr_completed += other.wr_completed;
        sectors_written += other.sectors_written;
        return *this;
    }

    data_sample_diff operator+(const data_sample_diff &other) const
    {
        data_sample_diff result = *this;
        result += other;
        return result;
    }

    std::chrono::time_point<std::chrono::system_clock> timestamp;
    uint32_t major{0};
    uint32_t minor{0};
    uint32_t index{0};
    std::string device{""};
    uint64_t rd_completed{0};
    uint64_t sectors_read{0};
    uint64_t wr_completed{0};
    uint64_t sectors_written{0};
};

struct data_sample_cumulated
{
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    uint64_t rd_completed{0};
    uint64_t sectors_read{0};
    uint64_t wr_completed{0};
    uint64_t sectors_written{0};

    data_sample_cumulated &operator+=(const data_sample_cumulated &other)
    {
        rd_completed += other.rd_completed;
        sectors_read += other.sectors_read;
        wr_completed += other.wr_completed;
        sectors_written += other.sectors_written;
        return *this;
    }

    data_sample_cumulated operator+(const data_sample_cumulated &other) const
    {
        data_sample_cumulated result = *this;
        result += other;
        return result;
    }
};
} // namespace rt_monitor::disk

namespace rt_monitor
{
template <> db_stream &db_stream::operator<< <disk::data_sample>(disk::data_sample sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    std::stringstream ss;
    ss << "disk_stats,hostname=" << hostname << ",device=" << sample.device << " ";
    ss << "sectors_read=" << sample.sectors_read << "i,"
       << "sectors_written=" << sample.sectors_written << "i";
    ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
    this->write_line(ss.str());
    return *this;
}

template <> db_stream &db_stream::operator<< <disk::data_sample_diff>(disk::data_sample_diff sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    std::stringstream ss;
    ss << "disk,hostname=" << hostname << ",device=" << sample.device << " ";
    ss << "Sectors_reads/s=" << sample.sectors_read << "i,"
       << "Sectors_writes/s=" << sample.sectors_written << "i,"
       << "Read_operations/s=" << sample.rd_completed << "i,"
       << "Write_operations/s=" << sample.wr_completed << "i";
    ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
    this->write_line(ss.str());
    return *this;
}

template <> db_stream &db_stream::operator<< <disk::data_sample_cumulated>(disk::data_sample_cumulated sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    std::stringstream ss;
    ss << "disk,hostname=" << hostname << ",device=total ";
    ss << "Sectors_reads/s=" << sample.sectors_read << "i,"
       << "Sectors_writes/s=" << sample.sectors_written << "i,"
       << "Read_operations/s=" << sample.rd_completed << "i,"
       << "Write_operations/s=" << sample.wr_completed << "i";
    ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
    this->write_line(ss.str());
    
    spdlog::debug("Sending cumulated disk sample to InfluxDB");

    return *this;
}

template <> file_stream &file_stream::operator<< <disk::data_sample>(disk::data_sample sample)
{
    io::write_binary(this->file_, sample.timestamp);
    io::write_binary(this->file_, sample.major);
    io::write_binary(this->file_, sample.minor);
    io::write_binary(this->file_, sample.index);
    io::write_binary(this->file_, sample.rd_completed);
    io::write_binary(this->file_, sample.rd_merged);
    io::write_binary(this->file_, sample.sectors_read);
    io::write_binary(this->file_, sample.time_read);
    io::write_binary(this->file_, sample.wr_completed);
    io::write_binary(this->file_, sample.wr_merged);
    io::write_binary(this->file_, sample.sectors_written);
    io::write_binary(this->file_, sample.time_write);
    io::write_binary(this->file_, sample.io_in_progress);
    io::write_binary(this->file_, sample.time_io);
    io::write_binary(this->file_, sample.time_weighted_io);
    io::write_binary(this->file_, sample.disc_completed);
    io::write_binary(this->file_, sample.disc_merged);
    io::write_binary(this->file_, sample.sectors_discarded);
    io::write_binary(this->file_, sample.time_discard);
    io::write_binary(this->file_, sample.flush_requests);
    io::write_binary(this->file_, sample.time_flush);
    return *this;
}
} // namespace rt_monitor

namespace rt_monitor::disk
{
std::vector<block_device_info> get_partition_block_sizes_binary()
{
    const std::string sys_block = "/sys/class/block";
    std::vector<block_device_info> entries;

    for (const auto &entry : std::filesystem::directory_iterator(sys_block))
    {
        std::string device_name = entry.path().filename().string();
        if (device_name.find("loop") != std::string::npos)
        {
            continue;
        }
        auto queue_path = entry.path() / "queue" / "logical_block_size";

        // If that file doesn't exist (typically for partitions), follow symlink to get parent
        if (!std::filesystem::exists(queue_path))
        {
            if (!entry.is_symlink())
            {
                continue;
            }

            std::error_code ec;
            const auto target = std::filesystem::read_symlink(entry, ec);
            if (ec || target.empty())
            {
                continue;
            }

            // Follow symlink to something and get to the block device directory
            auto parent = entry.path().parent_path() / target;
            parent = parent.parent_path();
            queue_path = parent / "queue" / "logical_block_size";

            if (!std::filesystem::exists(queue_path))
            {
                continue;
            }
        }

        std::ifstream bs_file(queue_path, std::ios::in);
        uint32_t block_size = 0;

        if (bs_file.is_open() && bs_file >> block_size)
        {
            entries.emplace_back(device_name, block_size);
        }
    }

    return entries;
}

void read_disk_samples(int fd, const std::unordered_map<std::string, size_t> &name_to_index,
                       std::unordered_map<uint32_t, data_sample> &samples_set)
{
    const auto now = std::chrono::system_clock::now();

    if (lseek(fd, 0, SEEK_SET) == -1) return;

    char buffer[65536]; // 64KB
    ssize_t bytes_read = pread(fd, buffer, sizeof(buffer) - 1, 0);
    if (bytes_read <= 0) return;
    buffer[bytes_read] = '\0';

    const char* ptr = buffer;
    const char* end = buffer + bytes_read;

    while (ptr < end)
    {
        const char* eol = static_cast<const char*>(std::memchr(ptr, '\n', end - ptr));
        const char* line_end = eol ? eol : end;
        
        const char* curr = ptr;
        
        // Skip leading spaces
        while (curr < line_end && std::isspace(*curr)) curr++;
        if (curr >= line_end) { ptr = eol ? eol + 1 : end; continue; }

        uint32_t major = 0, minor = 0;
        
        // 1. Major
        auto res1 = std::from_chars(curr, line_end, major);
        if (res1.ec != std::errc()) { ptr = eol ? eol + 1 : end; continue; }
        curr = res1.ptr;
        while (curr < line_end && std::isspace(*curr)) curr++;
        
        // 2. Minor
        auto res2 = std::from_chars(curr, line_end, minor);
        if (res2.ec != std::errc()) { ptr = eol ? eol + 1 : end; continue; }
        curr = res2.ptr;
        while (curr < line_end && std::isspace(*curr)) curr++;
        
        // 3. Device Name
        const char* name_start = curr;
        while (curr < line_end && !std::isspace(*curr)) curr++;
        std::string device(name_start, curr - name_start);

        if (device.starts_with("loop") || device.starts_with("dm"))
        {
            ptr = eol ? eol + 1 : end;
            continue;
        }

        const auto index_it = name_to_index.find(device);
        const uint32_t index =
            (index_it != name_to_index.cend()) ? index_it->second : std::numeric_limits<uint32_t>::max();
        if (index == std::numeric_limits<uint32_t>::max()) // Fixed comparison to match type
        {
            spdlog::error("disk sample partition name not indexed {}", device);
            ptr = eol ? eol + 1 : end;
            continue;
        }

        // 4. Parse metrics
        uint64_t v[17] = {0}; // rd_compl, rd_merged, s_read, t_read, wr_compl, wr_merged, s_written, t_write, io_prog, t_io, t_weighted, disc_compl, disc_merged, s_disc, t_disc, flush, t_flush
        int count = 0;
        
        while (curr < line_end && count < 17) {
             while (curr < line_end && std::isspace(*curr)) curr++;
             if (curr >= line_end) break;
             auto res = std::from_chars(curr, line_end, v[count]);
             if (res.ec == std::errc()) {
                 curr = res.ptr;
                 count++;
             } else {
                 break;
             }
        }
        
        // Assign values
        uint64_t rd_completed = v[0];
        uint64_t rd_merged = v[1];
        uint64_t sectors_read = v[2];
        uint64_t time_read = v[3];
        uint64_t wr_completed = v[4];
        uint64_t wr_merged = v[5];
        uint64_t sectors_written = v[6];
        uint64_t time_write = v[7];
        uint64_t io_in_progress = v[8];
        uint64_t time_io = v[9];
        uint64_t time_weighted_io = v[10];
        uint64_t disc_completed = v[11];
        uint64_t disc_merged = v[12];
        uint64_t sectors_discarded = v[13];
        uint64_t time_discard = v[14];
        uint64_t flush_requests = v[15];
        uint64_t time_flush = v[16];

        // Continue with existing logic...


        data_sample sample{now,
                           major,
                           minor,
                           index,
                           device,
                           rd_completed,
                           rd_merged,
                           sectors_read,
                           time_read,
                           wr_completed,
                           wr_merged,
                           sectors_written,
                           time_write,
                           io_in_progress,
                           time_io,
                           time_weighted_io,
                           disc_completed,
                           disc_merged,
                           sectors_discarded,
                           time_discard,
                           flush_requests,
                           time_flush};
        samples_set[index] = sample;

        spdlog::debug("disk monitoring sample: {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, "
                      "{}, {}, {}, {}",
                      std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count(), major,
                      minor, device, rd_completed, rd_merged, sectors_read, time_read, wr_completed, wr_merged,
                      sectors_written, time_write, io_in_progress, time_io, time_weighted_io, disc_completed,
                      disc_merged, sectors_discarded, time_discard, flush_requests, time_flush);

        ptr = eol ? eol + 1 : end;
    }
}


void disk_producer(double time_interval, 
                   const std::unordered_map<std::string, size_t>& name_to_index,
                   ThreadSafeQueue<std::unordered_map<uint32_t, data_sample>>& queue)
{
    int fd = open("/proc/diskstats", O_RDONLY);
    if (fd < 0) {
        spdlog::error("Failed to open /proc/diskstats");
        queue.stop();
        return;
    }

    bool sampling_warning_provided = false;
    while (!pause_manager::stopped())
    {
        pause_manager::wait_if_paused();

        const auto begin = std::chrono::high_resolution_clock::now();
        
        std::unordered_map<uint32_t, data_sample> samples;
        read_disk_samples(fd, name_to_index, samples);
        queue.push(std::move(samples));

        const auto end = std::chrono::high_resolution_clock::now();
        const auto sampling_time = std::chrono::duration_cast<std::chrono::milliseconds>(end - begin).count();
        auto time_to_wait = time_interval - sampling_time;
        if (time_to_wait < 0.)
        {
            if (!sampling_warning_provided)
            {
                spdlog::warn("The sampling period of {} ms might be too low for disk monitoring. The last sampling "
                             "time was {} ms. Samples might be missed. Consider reducing the sampling frequency.",
                             static_cast<int>(time_interval), sampling_time);
                sampling_warning_provided = true;
            }
            time_to_wait = 0.;
        }
        pause_manager::sleep_for(std::chrono::milliseconds(static_cast<int64_t>(time_to_wait)));
    }
    close(fd);
    queue.stop();
    spdlog::trace("disk producer stopped");
}

template <typename stream_type> void start_sampling(double time_interval, stream_type &&stream);

template <> void start_sampling(const double time_interval, db_stream &&stream)
{
    spdlog::trace("starting disk monitoring");
    const auto partition_info = get_partition_block_sizes_binary();
    spdlog::debug("identified {} partitions to monitor", partition_info.size());

    std::unordered_map<std::string, size_t> name_to_index;
    for (size_t i = 0; i < partition_info.size(); ++i)
    {
        name_to_index[partition_info[i].name] = i;
    }

    ThreadSafeQueue<std::unordered_map<uint32_t, data_sample>> queue;
    std::thread producer_thread(disk_producer, time_interval, std::cref(name_to_index), std::ref(queue));

    std::unordered_map<uint32_t, data_sample> current_sample_set;
    while (queue.pop(current_sample_set))
    {
        if (pause_manager::stopped()) break;
        spdlog::debug("Collected disk samples for {} partitions", current_sample_set.size());
        
        for (const auto [index, current_sample] : current_sample_set)
        {
            stream << current_sample;
        }
    }
    
    producer_thread.join();
    spdlog::trace("disk monitoring stopped");
}

template <> void start_sampling(const double time_interval, file_stream &&stream)
{
    spdlog::trace("starting disk monitoring");
    const auto partition_info = get_partition_block_sizes_binary();
    spdlog::debug("identified {} partitions to monitor", partition_info.size());

    std::unordered_map<std::string, size_t> name_to_index;
    for (size_t i = 0; i < partition_info.size(); ++i)
    {
        name_to_index[partition_info[i].name] = i;
    }

    io::write_binary(stream.get_file(), static_cast<uint32_t>(partition_info.size()));
    for (const auto info : partition_info)
    {
        io::write_binary(stream.get_file(), static_cast<uint32_t>(info.name.size()));
        io::write_binary(stream.get_file(), info.name);
        io::write_binary(stream.get_file(), info.block_size);
        spdlog::debug("partition: {}, block size: {}", info.name, info.block_size);
    }

    ThreadSafeQueue<std::unordered_map<uint32_t, data_sample>> queue;
    std::thread producer_thread(disk_producer, time_interval, std::cref(name_to_index), std::ref(queue));

    std::unordered_map<uint32_t, data_sample> samples_set;
    while (queue.pop(samples_set))
    {
        if (pause_manager::stopped()) break;
        for (const auto &[index, sample] : samples_set)
        {
            stream << sample;
        }
    }
    producer_thread.join();
    spdlog::trace("disk monitoring stopped");
}
} // namespace rt_monitor::disk