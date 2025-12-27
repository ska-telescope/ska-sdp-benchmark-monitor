#include <filesystem>
#include <scn/scan.h>
#include <thread>

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
    auto point = influxdb::Point{"disk"}
                     .addTag("hostname", hostname)
                     .addTag("device", sample.device)
                     .addField("Sectors_reads/s", static_cast<long long int>(sample.sectors_read))
                     .addField("Sectors_writes/s", static_cast<long long int>(sample.sectors_written))
                     .addField("Read_operations/s", static_cast<long long int>(sample.rd_completed))
                     .addField("Write_operations/s", static_cast<long long int>(sample.wr_completed))
                     .setTimestamp(sample.timestamp);
    try
    {
        this->db_ptr_->write(std::move(point));
    }
    catch (std::runtime_error e)
    {
        spdlog::error(std::string{"Error while pushing a disk sample: "} + e.what());
    }

    return *this;
}

template <> db_stream &db_stream::operator<< <disk::data_sample_diff>(disk::data_sample_diff sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    auto point = influxdb::Point{"disk"}
                     .addTag("hostname", hostname)
                     .addTag("device", sample.device)
                     .addField("Sectors_reads/s", static_cast<long long int>(sample.sectors_read))
                     .addField("Sectors_writes/s", static_cast<long long int>(sample.sectors_written))
                     .addField("Read_operations/s", static_cast<long long int>(sample.rd_completed))
                     .addField("Write_operations/s", static_cast<long long int>(sample.wr_completed))
                     .setTimestamp(sample.timestamp);
    try
    {
        this->db_ptr_->write(std::move(point));
    }
    catch (std::runtime_error e)
    {
        spdlog::error(std::string{"Error while pushing a disk sample: "} + e.what());
    }

    return *this;
}

template <> db_stream &db_stream::operator<< <disk::data_sample_cumulated>(disk::data_sample_cumulated sample)
{
    static const std::string hostname = rt_monitor::io::get_hostname();
    auto point = influxdb::Point{"disk"}
                     .addTag("hostname", hostname)
                     .addTag("device", "total")
                     .addField("Sectors_reads/s", static_cast<long long int>(sample.sectors_read))
                     .addField("Sectors_writes/s", static_cast<long long int>(sample.sectors_written))
                     .addField("Read_operations/s", static_cast<long long int>(sample.rd_completed))
                     .addField("Write_operations/s", static_cast<long long int>(sample.wr_completed))
                     .setTimestamp(sample.timestamp);
    
    spdlog::debug("Sending cumulated disk sample to InfluxDB");

    try
    {
        this->db_ptr_->write(std::move(point));
    }
    catch (std::runtime_error e)
    {
        spdlog::error(std::string{"Error while pushing a disk sample: "} + e.what());
    }

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

void read_disk_samples(const std::unordered_map<std::string, size_t> &name_to_index,
                       std::unordered_map<uint32_t, data_sample> &samples_set)
{
    const auto now = std::chrono::system_clock::now();

    std::ifstream input("/proc/diskstats");
    std::string line;
    while (std::getline(input, line))
    {
        std::istringstream line_stream(line);
        auto [major, minor, device, rd_completed, rd_merged, sectors_read, time_read, wr_completed, wr_merged,
              sectors_written, time_write, io_in_progress, time_io, time_weighted_io, disc_completed, disc_merged,
              sectors_discarded, time_discard, flush_requests, time_flush] =
            scn::scan<uint32_t, uint32_t, std::string, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
                      uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
                      uint64_t, uint64_t>(line, "{} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {}")
                ->values();
        if (device.starts_with("loop") || device.starts_with("dm"))
        {
            continue;
        }

        const auto index_it = name_to_index.find(device);
        const uint32_t index =
            (index_it != name_to_index.cend()) ? index_it->second : std::numeric_limits<uint32_t>::max();
        if (index == -1)
        {
            spdlog::error("disk sample partition name not indexed {}", device);
            continue;
        }

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
    }
}

void disk_producer(double time_interval, 
                   const std::unordered_map<std::string, size_t>& name_to_index,
                   ThreadSafeQueue<std::unordered_map<uint32_t, data_sample>>& queue)
{
    bool sampling_warning_provided = false;
    while (!pause_manager::stopped())
    {
        pause_manager::wait_if_paused();

        const auto begin = std::chrono::high_resolution_clock::now();
        
        std::unordered_map<uint32_t, data_sample> samples;
        read_disk_samples(name_to_index, samples);
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

    std::unordered_map<uint32_t, data_sample> last_sample_set;
    if (!queue.pop(last_sample_set))
    {
        producer_thread.join();
        return;
    }

    std::unordered_map<uint32_t, data_sample> current_sample_set;
    while (queue.pop(current_sample_set))
    {
        if (pause_manager::stopped()) break;
        spdlog::debug("Collected disk samples for {} partitions", current_sample_set.size());
        data_sample_cumulated cumulated_sample_diff;
        if (!current_sample_set.empty()) {
             cumulated_sample_diff.timestamp = current_sample_set.begin()->second.timestamp;
        } else {
             cumulated_sample_diff.timestamp = std::chrono::system_clock::now();
        }

        for (const auto [index, current_sample] : current_sample_set)
        {
            const auto last_sample_it = last_sample_set.find(index);
            if (last_sample_it != last_sample_set.end())
            {
                const auto &last_sample = last_sample_it->second;
                data_sample_diff sample_diff{partition_info[index].block_size, current_sample - last_sample};
                cumulated_sample_diff.rd_completed += sample_diff.rd_completed;
                cumulated_sample_diff.wr_completed += sample_diff.wr_completed;
                cumulated_sample_diff.sectors_read += sample_diff.sectors_read;
                cumulated_sample_diff.sectors_written += sample_diff.sectors_written;
            }
        }

        stream << cumulated_sample_diff;
        last_sample_set = std::move(current_sample_set);
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