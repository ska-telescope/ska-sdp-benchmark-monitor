#include "variable_monitor.h"
#include "monitor_io.h"
#include "db_stream.hpp"
#include "file_stream.hpp"
#include <chrono>
#include <string>
#include <spdlog/spdlog.h>

namespace rt_monitor::variable
{
    struct data_sample {
        std::chrono::time_point<std::chrono::system_clock> timestamp;
    };
}

namespace rt_monitor {
    template <> db_stream &db_stream::operator<< <variable::data_sample>(variable::data_sample sample)
    {
        static const std::string hostname = rt_monitor::io::get_hostname();
        influxdb::Point point{"variable"};
        auto stamp = std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
        point.addTag("hostname", hostname)
             .addField("stamp", static_cast<long long>(stamp))
             .setTimestamp(sample.timestamp);
        try {
            this->db_ptr_->write(std::move(point));
        } catch (const std::runtime_error &e) {
            spdlog::error(std::string{"Error while pushing a variable sample: "} + e.what());
        }
        return *this;
    }

    template <> file_stream &file_stream::operator<< <variable::data_sample>(variable::data_sample sample)
    {
        io::write_binary(this->file_, sample.timestamp.time_since_epoch().count());
        return *this;
    }
}

namespace rt_monitor::variable
{
    template <typename Stream>
    void start_sampling(Stream &&stream)
    {
        data_sample sample;
        sample.timestamp = std::chrono::system_clock::now();
        stream << sample;
        stream.flush();
    }

    template void start_sampling<file_stream>(file_stream&&);
    template void start_sampling<db_stream>(db_stream&&);
}
