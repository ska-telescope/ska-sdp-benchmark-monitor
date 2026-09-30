#pragma once
#include <cstdint>
#include <fstream>
#include <limits>
#include <ostream>
#include <vector>

namespace rt_monitor::io
{
/**
 * @brief Creates and returns a binary output file stream with a custom buffer size.
 *
 * This function opens a file with the specified filename in binary mode and sets a custom buffer of 16 MB for the file
 * stream to potentially improve I/O performance.
 *
 * @param filename The name of the file to open for binary output.
 * @return std::ofstream The output file stream with the custom buffer set.
 *
 * @note The buffer is local to the function and will be destroyed when the function returns, which may lead to
 * undefined behavior. Consider managing the buffer's lifetime appropriately.
 */
inline std::ofstream make_buffer(std::string filename)
{
    std::ofstream file(filename, std::ios::binary);

    const size_t buffer_size = 16 * 1024 * 1024;
    std::vector<char> buffer(buffer_size);

    file.rdbuf()->pubsetbuf(buffer.data(), buffer.size());
    return file;
}

/**
 * @brief Retrieves the hostname of the system.
 * @return std::string The hostname.
 */
std::string get_hostname();

/**
 * @brief Converts a CPU identifier string to an unsigned integer.
 *
 * @param str The CPU identifier string. If the string is "cpu", the function
 *            returns the maximum value of uint32_t. Otherwise, it extracts
 *            the numeric part of the string (after "cpu") and converts it to
 *            an integer.
 * @return uint32_t The converted CPU identifier as an unsigned integer.
 */
inline uint32_t cpuid_str_to_uint(const std::string &str)
{
    return str == "cpu" ? std::numeric_limits<uint32_t>::max() : std::stoi(str.substr(3));
}

/**
 * @brief Writes a value to a binary or text stream.
 *
 * @tparam T The type of the value to be written.
 * @param stream The output stream to write to.
 * @param value The value to be written to the stream.
 */
template <typename T> void write_binary(std::ostream &stream, const T value)
{
    stream.write(reinterpret_cast<const char *>(&value), sizeof(value));
}

/**
 * @brief Executes a shell command and captures its output.
 *
 * @param command The shell command to execute.
 * @return std::string The output of the executed command.
 */
std::string exec(const std::string &command);

/**
 * @brief Specialization of the write_binary function for std::string.
 *
 * @param stream The output stream to write to.
 * @param value The string value to be written to the stream.
 */
template <> void write_binary(std::ostream &stream, const std::string value);
} // namespace rt_monitor::io
