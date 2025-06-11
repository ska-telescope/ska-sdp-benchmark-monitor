#include <array>
#include <chrono>
#include <cstring>
#include <fstream>
#include <scn/scan.h>
#include <spdlog/spdlog.h>
#include <thread>

#include "monitor_io.h"
#include "pause_manager.h"

namespace rt_monitor::disk
{
void read_disk_sample(std::ostream &file)
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
            continue;

        io::write_binary(file, timestamp);
        io::write_binary(file, major);
        io::write_binary(file, minor);
        std::array<char, 32> device_char;
        std::fill(device_char.begin(), device_char.end(), '\0');
        const size_t device_name_size = std::min(device_char.size(), device.size());
        std::copy_n(device.cbegin(), device_name_size, device_char.begin());
        io::write_binary(file, device_char);
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
    }
}

void start(const double time_interval, const std::string &out_path)
{
    bool sampling_warning_provided = false;

    auto file = io::make_buffer(out_path);

    const uint64_t n_major_blocks = std::stoi(io::exec("lsblk -d -o NAME --noheadings | grep -v loop | wc -l"));
    const uint64_t n_all_blocks = std::stoi(io::exec("lsblk -o NAME --noheadings | grep -v loop | wc -l"));
    const std::string sector_size_str = io::exec("lsblk -d -o NAME,PHY-SEC --noheadings | grep -v loop | awk '{printf "
                                                 "\"%s,%s,\", $1, $2}' | sed 's/,$/\\n/'");
    io::write_binary(file, n_major_blocks);
    io::write_binary(file, n_all_blocks);
    io::write_binary(file, sector_size_str + "\n");

    while (!pause_manager::stopped())
    {
        if (pause_manager::paused())
        {
            spdlog::trace("disk monitoring paused");
            std::unique_lock<std::mutex> lock(pause_manager::mutex());
            pause_manager::condition_variable().wait(lock, [] { return !pause_manager::paused().load(); });
        }
        const auto begin = std::chrono::high_resolution_clock::now();
        read_disk_sample(file);
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