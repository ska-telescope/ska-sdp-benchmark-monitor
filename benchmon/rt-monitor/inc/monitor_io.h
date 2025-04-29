#pragma once
#include <cstdint>
#include <fstream>
#include <limits>
#include <ostream>
#include <vector>
#define BINARY

namespace rt_monitor::io
{
inline std::ofstream make_buffer(std::string filename)
{
    std::ofstream file(filename, std::ios::binary);

    const size_t buffer_size = 16 * 1024 * 1024; // 1 MB, for example
    std::vector<char> buffer(buffer_size);

    file.rdbuf()->pubsetbuf(buffer.data(), buffer.size());
    return file;
}

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
 * @return std::ostream& A reference to the output stream.
 *
 * @note If the macro BINARY is defined, the value is written in binary format.
 *       Otherwise, the value is written in text format followed by a comma.
 */
template <typename T> std::ostream &write_binary(std::ostream &stream, const T value)
{
#ifndef BINARY
    stream << value << ",";
#else
    stream.write(reinterpret_cast<const char *>(&value), sizeof(value));
#endif
    return stream;
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
 * @return std::ostream& A reference to the output stream.
 */
template <> std::ostream &write_binary(std::ostream &stream, const std::string value);
} // namespace rt_monitor::io