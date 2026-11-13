#include <algorithm>
#include <array>
#include <memory>
#include <unistd.h>

#include "monitor_io.h"

namespace rt_monitor::io
{
std::string get_hostname()
{
    char hostname[1024];
    if (gethostname(hostname, sizeof(hostname)) == 0)
    {
        return std::string(hostname);
    }
    return "unknown";
}

template <> void write_binary(std::ostream &stream, std::string arr)
{
    stream << arr;
}

std::string exec(const std::string &command)
{
    std::array<char, 32> buffer;
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