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

    void ib_producer(double interval_ms, ThreadSafeQueue<data_sample>& queue) {
        std::vector<std::string> ib_devices;
        if (fs::exists("/sys/class/infiniband")) {
            for (const auto &entry : fs::directory_iterator("/sys/class/infiniband")) {
                ib_devices.push_back(entry.path().filename().string());
            }
        }

        if (ib_devices.empty()) {
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

            for (const auto &device : ib_devices) {
                std::string xmit_path = "/sys/class/infiniband/" + device + "/ports/1/counters/port_xmit_data";
                std::string rcv_path = "/sys/class/infiniband/" + device + "/ports/1/counters/port_rcv_data";

                try {
                    std::ifstream xmit_file(xmit_path);
                    std::ifstream rcv_file(rcv_path);
                    
                    if (xmit_file.is_open() && rcv_file.is_open()) {
                        uint64_t xmit_val, rcv_val;
                        xmit_file >> xmit_val;
                        rcv_file >> rcv_val;
                        sample.ports.push_back({device, xmit_val, rcv_val});
                    }
                } catch (...) {
                    // Ignore errors
                }
            }
            
            queue.push(std::move(sample));

            auto end = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
            if (elapsed < sleep_duration)
            {
                pause_manager::sleep_for(sleep_duration - elapsed);
            }
        }
        queue.stop();
    }
}

namespace rt_monitor {
    template <> db_stream &db_stream::operator<< <ib::data_sample>(ib::data_sample sample)
    {
        static const std::string hostname = rt_monitor::io::get_hostname();
        for (const auto& port : sample.ports) {
            influxdb::Point point{"infiniband"};
            point.addTag("hostname", hostname)
                 .addTag("device", port.device)
                 .addField("port_rcv_data", static_cast<long long>(port.port_rcv_data))
                 .addField("port_xmit_data", static_cast<long long>(port.port_xmit_data))
                 .setTimestamp(sample.timestamp);
            try {
                this->db_ptr_->write(std::move(point));
            } catch (const std::runtime_error &e) {
                spdlog::error(std::string{"Error while pushing an IB sample: "} + e.what());
            }
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
