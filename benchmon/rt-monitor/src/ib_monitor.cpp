#include "ib_monitor.h"
#include "pause_manager.h"
#include "monitor_io.h"
#include "db_stream.hpp"
#include "file_stream.hpp"
#include "thread_safe_queue.hpp"
#include <filesystem>
#include <fstream>
#include <thread>
#include <chrono>
#include <spdlog/spdlog.h>
#include <fcntl.h>
#include <unistd.h>
#include <charconv>

namespace rt_monitor::ib
{
    namespace fs = std::filesystem;

    struct ib_port_data {
        std::string device;
        uint64_t port_xmit_data;
        uint64_t port_rcv_data;
    };

    struct data_sample {
        std::chrono::time_point<std::chrono::system_clock> timestamp;
        std::vector<ib_port_data> ports;
    };

    struct IbSource {
        std::string device;
        int xmit_fd;
        int rcv_fd;
    };

    std::vector<IbSource> get_ib_sources() {
        std::vector<IbSource> sources;
        if (fs::exists("/sys/class/infiniband")) {
            for (const auto &entry : fs::directory_iterator("/sys/class/infiniband")) {
                std::string device = entry.path().filename().string();
                std::string xmit_path = "/sys/class/infiniband/" + device + "/ports/1/counters/port_xmit_data";
                std::string rcv_path = "/sys/class/infiniband/" + device + "/ports/1/counters/port_rcv_data";
                
                int xmit_fd = open(xmit_path.c_str(), O_RDONLY);
                int rcv_fd = open(rcv_path.c_str(), O_RDONLY);

                if (xmit_fd >= 0 && rcv_fd >= 0) {
                    sources.push_back({device, xmit_fd, rcv_fd});
                } else {
                    if (xmit_fd >= 0) close(xmit_fd);
                    if (rcv_fd >= 0) close(rcv_fd);
                    spdlog::warn("Failed to open IB counters for device {}", device);
                }
            }
        }
        return sources;
    }

    uint64_t read_value(int fd) {
        char buffer[32];
        ssize_t bytes = pread(fd, buffer, sizeof(buffer) - 1, 0);
        if (bytes > 0) {
            buffer[bytes] = '\0';
            uint64_t val = 0;
            std::from_chars(buffer, buffer + bytes, val);
            return val;
        }
        return 0;
    }

    void ib_producer(double interval_ms, ThreadSafeQueue<data_sample>& queue) {
        auto sources = get_ib_sources();

        if (sources.empty()) {
            spdlog::warn("No InfiniBand devices found.");
            queue.stop();
            return;
        }

        const auto sleep_duration = std::chrono::milliseconds(static_cast<long long>(interval_ms));

        while (!pause_manager::stopped())
        {
            if (pause_manager::paused())
            {
                std::unique_lock<std::mutex> lock(pause_manager::mutex());
                pause_manager::condition_variable().wait(lock, [] { return !pause_manager::paused().load(); });
            }
            auto start = std::chrono::steady_clock::now();
            
            data_sample sample;
            sample.timestamp = std::chrono::system_clock::now();

            for (const auto &source : sources) {
                uint64_t xmit_val = read_value(source.xmit_fd);
                uint64_t rcv_val = read_value(source.rcv_fd);
                sample.ports.push_back({source.device, xmit_val, rcv_val});
            }
            
            queue.push(std::move(sample));

            auto end = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
            if (elapsed < sleep_duration)
            {
                pause_manager::sleep_for(sleep_duration - elapsed);
            }
        }
        
        for (const auto& source : sources) {
            close(source.xmit_fd);
            close(source.rcv_fd);
        }
        queue.stop();
    }
}

namespace rt_monitor {
    template <> db_stream &db_stream::operator<< <ib::data_sample>(ib::data_sample sample)
    {
        static const std::string hostname = rt_monitor::io::get_hostname();
        for (const auto& port : sample.ports) {
            std::stringstream ss;
            ss << "infiniband,hostname=" << hostname << ",device=" << port.device << " ";
            ss << "port_rcv_data=" << port.port_rcv_data << "i,"
               << "port_xmit_data=" << port.port_xmit_data << "i";
            ss << " " << std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
            this->write_line(ss.str());
        }
        return *this;
    }

    template <> file_stream &file_stream::operator<< <ib::data_sample>(ib::data_sample sample)
    {
        io::write_binary(this->file_, sample.timestamp.time_since_epoch().count());
        io::write_binary(this->file_, static_cast<uint32_t>(sample.ports.size()));
        for (const auto& port : sample.ports) {
            io::write_binary(this->file_, port.device);
            io::write_binary(this->file_, port.port_rcv_data);
            io::write_binary(this->file_, port.port_xmit_data);
        }
        return *this;
    }
}

namespace rt_monitor::ib {
    template <typename Stream>
    void start_sampling(double interval_ms, Stream &&stream)
    {
        ThreadSafeQueue<data_sample> queue;
        std::thread producer_thread(ib_producer, interval_ms, std::ref(queue));

        data_sample sample;
        while (queue.pop(sample))
        {
            if (pause_manager::stopped()) break;
            stream << sample;
        }
        producer_thread.join();
        spdlog::trace("IB monitoring stopped");
    }

    template void start_sampling<file_stream>(double, file_stream&&);
    template void start_sampling<db_stream>(double, db_stream&&);
}
