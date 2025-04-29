#include <algorithm>
#include <array>
#include <memory>
#include <monitor_io.h>

namespace rt_monitor::io
{
template <> std::ostream &write_binary(std::ostream &stream, std::string arr)
{
#ifndef BINARY
    stream << arr << ",";
#else
    stream << arr;
#endif
    return stream;
}

std::string exec(const std::string &command)
{
    std::array<char, 128> buffer;
    std::string result;

    if (auto pipe = std::unique_ptr<FILE, int (*)(FILE *)>(popen(command.c_str(), "r"), pclose))
    {
        while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr)
        {
            result += buffer.data();
        }
    }
    else
    {
        throw std::runtime_error("Command " + command + " failed.");
    }

    result.erase(std::remove_if(result.begin(), result.end(), ::isspace), result.end());
    return result;
}
} // namespace rt_monitor::io