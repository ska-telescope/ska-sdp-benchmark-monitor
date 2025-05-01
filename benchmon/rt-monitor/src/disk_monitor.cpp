#include "monitor_io.h"
#include <array>
#include <chrono>
#include <cstring>
#include <fstream>
#include <memory>
#include <scn/scan.h>
#include <thread>

namespace rt_monitor::disk
{
void start(const double time_interval, const std::string &out_path, const bool &running)
{
    auto file = io::make_buffer(out_path);

    const uint64_t n_major_blocks = std::stoi(io::exec("lsblk -d -o NAME --noheadings | grep -v loop | wc -l"));
    const uint64_t n_all_blocks = std::stoi(io::exec("lsblk -o NAME --noheadings | grep -v loop | wc -l"));
    const std::string sector_size_str = io::exec("lsblk -d -o NAME,PHY-SEC --noheadings | grep -v loop | awk '{printf "
                                                 "\"%s,%s,\", $1, $2}' | sed 's/,$/\\n/'");
    io::write_binary(file, n_major_blocks);
    io::write_binary(file, n_all_blocks);
    io::write_binary(file, sector_size_str + "\n");

    while (running)
    {
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
#ifndef BINARY
            file << std::endl;
#endif
        }
        std::this_thread::sleep_for(std::chrono::microseconds(static_cast<int64_t>(time_interval * 1000)));
    }
}
} // namespace rt_monitor::disk