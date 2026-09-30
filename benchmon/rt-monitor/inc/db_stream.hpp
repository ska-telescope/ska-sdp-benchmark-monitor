#pragma once
#include <InfluxDB.h>
#include <InfluxDBFactory.h>
#include <memory>
#include <spdlog/spdlog.h>
#include <string>

namespace rt_monitor
{
/**
 * @class db_stream
 * @brief A wrapper class for managing an InfluxDB database stream.
 *
 * This class encapsulates an InfluxDB client, providing a convenient interface
 * for configuring batch buffer size, flushing data, and streaming data points
 * into the database. It manages the lifetime of the underlying InfluxDB client
 * using a unique pointer, ensuring proper resource management.
 *
 * Copy construction and copy assignment are disabled to prevent multiple
 * instances from managing the same database connection. Move semantics are
 * supported for efficient transfer of ownership.
 */
class db_stream
{
  public:
    /**
     * @brief Constructs a db_stream object and connects to the specified InfluxDB address.
     * @param influxdb_address The address (URL) of the InfluxDB instance.
     */
    db_stream(const std::string &influxdb_address)
    {
        db_ptr_ = influxdb::InfluxDBFactory::Get(influxdb_address);
    }

    db_stream(const db_stream &) = delete;
    db_stream &operator=(const db_stream &) = delete;
    db_stream(db_stream &&) = default;
    db_stream &operator=(db_stream &&) = default;

    /**
     * @brief Sets the batch buffer size for the InfluxDB client.
     * @param size The number of data points to buffer before writing to the database.
     */
    void set_buffer_size(const size_t size)
    {
        db_ptr_->batchOf(size);
    }

    /**
     * @brief Gets the current batch buffer size.
     * @return The number of data points currently set for batching.
     */
    size_t get_buffer_size() const
    {
        return db_ptr_->batchSize();
    }

    /**
     * @brief Flushes the current batch buffer, writing all buffered data points to the database.
     */
    void flush()
    {
        return db_ptr_->flushBatch();
    }

    /**
     * @brief Streams a data point or value into the database.
     * @tparam T The type of the data point or value to stream.
     * @param value The value to stream into the database.
     * @return Reference to this db_stream object for chaining.
     */
    template <typename T> db_stream &operator<<(T);

  private:
    /**
     * @brief Unique pointer to the underlying InfluxDB client.
     */
    std::unique_ptr<influxdb::InfluxDB> db_ptr_;
};
} // namespace rt_monitor