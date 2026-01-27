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
        std::stringstream ss;
        auto stamp = std::chrono::duration_cast<std::chrono::nanoseconds>(sample.timestamp.time_since_epoch()).count();
        ss << "variable,hostname=" << hostname << " ";
        ss << "stamp=" << stamp << "i";
        ss << " " << stamp;
        this->write_line(ss.str());
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
