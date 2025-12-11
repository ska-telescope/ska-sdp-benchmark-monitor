#pragma once
#include <fstream>
#include <string>

/**
 * @namespace rt_monitor
 * @brief Contains classes and utilities for real-time monitoring and file streaming.
 */
namespace rt_monitor
{
/**
 * @class file_stream
 * @brief A wrapper class for std::ofstream providing additional file streaming utilities.
 *
 * This class manages an output file stream and provides methods to control
 * buffering, flushing, and stream access. It is designed to facilitate
 * efficient file output operations in real-time monitoring scenarios.
 */
class file_stream
{
  public:
    /**
     * @brief Constructs a file_stream and opens the specified file for output.
     * @param filename The name of the file to open for writing.
     */
    file_stream(const std::string &filename) : file_(filename)
    {
        if (!file_.is_open() || !file_.good())
        {
            throw std::runtime_error("Failed to open file: " + filename);
        }
    }

    /**
     * @brief Sets the buffer size for the file stream.
     * @param size The desired buffer size in bytes.
     */
    void set_buffer_size(const size_t size)
    {
    }

    /**
     * @brief Gets the current buffer size of the file stream.
     * @return The buffer size in bytes.
     */
    size_t get_buffer_size() const
    {
        return 0;
    }

    /**
     * @brief Flushes the file stream, ensuring all buffered data is written to disk.
     */
    void flush()
    {
        file_.flush();
    }

    /**
     * @brief Provides access to the underlying std::ofstream object.
     * @return Reference to the internal std::ofstream.
     */
    std::ofstream &get_file()
    {
        return file_;
    }

    /**
     * @brief Writes data to the file stream using the stream insertion operator.
     * @tparam T The type of data to write.
     * @param value The data to write to the file stream.
     * @return Reference to this file_stream object.
     */
    template <typename T> file_stream &operator<<(T);

    file_stream(const file_stream &) = delete;
    file_stream &operator=(const file_stream &) = delete;
    file_stream(file_stream &&) = default;
    file_stream &operator=(file_stream &&) = default;

  private:
    /**
     * @brief Underlying file stream.
     */
    std::ofstream file_;
};
} // namespace rt_monitor