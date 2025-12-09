#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <scn/scan.h>
#include <spdlog/spdlog.h>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include "monitor_io.h"
#include "pause_manager.h"
#include "spdlog/common.h"

namespace rt_monitor::disk
{
struct block_device_info
{
    std::string name;
    uint32_t block_size;
};

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

void read_disk_sample(const std::unordered_map<std::string, size_t> &name_to_index, std::ostream &file)
{
    spdlog::trace("reading a disk monitoring sample");
    const auto now = std::chrono::system_clock::now();
    const auto duration = now.time_since_epoch();
    const auto timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();

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

        io::write_binary(file, timestamp);
        io::write_binary(file, major);
        io::write_binary(file, minor);
        io::write_binary(file, index);
        io::write_binary(file, rd_completed);
        io::write_binary(file, rd_merged);
        io::write_binary(file, sectors_read);
        io::write_binary(file, time_read);
        io::write_binary(file, wr_completed);
        io::write_binary(file, wr_merged);
        io::write_binary(file, sectors_written);
        io::write_binary(file, time_write);
        io::write_binary(file, io_in_progress);
        io::write_binary(file, time_io);
        io::write_binary(file, time_weighted_io);
        io::write_binary(file, disc_completed);
        io::write_binary(file, disc_merged);
        io::write_binary(file, sectors_discarded);
        io::write_binary(file, time_discard);
        io::write_binary(file, flush_requests);
        io::write_binary(file, time_flush);

        spdlog::debug("disk monitoring sample: {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, "
                      "{}, {}, {}, {}",
                      timestamp, major, minor, device, rd_completed, rd_merged,
                      sectors_read, time_read, wr_completed, wr_merged, sectors_written, time_write, io_in_progress,
                      time_io, time_weighted_io, disc_completed, disc_merged, sectors_discarded, time_discard,
                      flush_requests, time_flush);
    }
}

void start(const double time_interval, const std::string &out_path)
{
    spdlog::trace("starting disk monitoring");
    const auto partition_info = get_partition_block_sizes_binary();
    spdlog::debug("identified {} partitions to monitor", partition_info.size());

    bool sampling_warning_provided = false;

    auto file = io::make_buffer(out_path);
    io::write_binary(file, static_cast<uint32_t>(partition_info.size()));
    for (const auto info : partition_info)
    {
        io::write_binary(file, static_cast<uint32_t>(info.name.size()));
        io::write_binary(file, info.name);
        io::write_binary(file, info.block_size);
        spdlog::debug("partition: {}, block size: {}", info.name, info.block_size);
    }

    std::unordered_map<std::string, size_t> name_to_index;
    for (size_t i = 0; i < partition_info.size(); ++i)
    {
        name_to_index[partition_info[i].name] = i;
    }

    while (!pause_manager::stopped())
    {
        if (pause_manager::paused())
        {
            spdlog::trace("disk monitoring paused");
            std::unique_lock<std::mutex> lock(pause_manager::mutex());
            pause_manager::condition_variable().wait(lock, [] { return !pause_manager::paused().load(); });
        }
        const auto begin = std::chrono::high_resolution_clock::now();
        read_disk_sample(name_to_index, file);
        const auto end = std::chrono::high_resolution_clock::now();
        const auto sampling_time = std::chrono::duration_cast<std::chrono::milliseconds>(end - begin).count();
        auto time_to_wait = time_interval - sampling_time;
        if (time_to_wait < 0.)
        {
            if (!sampling_warning_provided)
            {
                spdlog::warn(
                    "The sampling period of {} ms might be too low for disk monitoring. The last sampling time "
                    "was {} ms. Samples might be missed. Consider reducing the sampling frequency.",
                    static_cast<int>(time_interval), sampling_time);
                sampling_warning_provided = true;
            }
            time_to_wait = 0.;
        }
        std::this_thread::sleep_for(std::chrono::microseconds(static_cast<int64_t>(time_interval * 1000)));
    }
    spdlog::trace("disk monitoring stopped");
}
} // namespace rt_monitor::disk