#pragma once
#include <string>
#include <vector>
#include <sstream>
#include <spdlog/spdlog.h>
#include <cstring>
#include <iostream>
#include <thread>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <memory>
#include <curl/curl.h>

namespace rt_monitor
{

class AsyncInfluxDBWriter {
public:
    AsyncInfluxDBWriter(const std::string& host, int port, const std::string& db_name) 
        : host_(host), port_(port), db_name_(db_name) {
        running_ = true;
        worker_ = std::thread(&AsyncInfluxDBWriter::worker_loop, this);
    }
    
    ~AsyncInfluxDBWriter() {
        stop();
    }

    void push(std::string&& data) {
        {
            std::unique_lock<std::mutex> lock(mutex_);
            queue_.push(std::move(data));
        }
        cv_.notify_one();
    }

    void stop() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            running_ = false;
        }
        cv_.notify_all();
        if (worker_.joinable()) worker_.join();
    }

private:
    std::string host_;
    int port_;
    std::string db_name_;
    std::thread worker_;
    std::queue<std::string> queue_;
    std::mutex mutex_;
    std::condition_variable cv_;
    bool running_;

    void worker_loop() {
        CURL* curl = curl_easy_init();
        if (!curl) {
            spdlog::error("Failed to initialize CURL");
            return;
        }

        std::string url = "http://" + host_ + ":" + std::to_string(port_) + "/write?db=" + db_name_;
        
        // Set constant options once
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 2L); // 2 seconds timeout
        curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 1L); // 1 second connect timeout
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_TCP_KEEPALIVE, 1L); // Enable TCP Keep-Alive

        while (true) {
            std::string payload;
            {
                std::unique_lock<std::mutex> lock(mutex_);
                cv_.wait(lock, [this] { return !queue_.empty() || !running_; });
                
                if (queue_.empty() && !running_) {
                    break;
                }
                
                if (!queue_.empty()) {
                    payload = std::move(queue_.front());
                    queue_.pop();
                }
            }

            if (!payload.empty()) {
                // Only update the payload for each request
                curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload.c_str());
                curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, (long)payload.length());

                CURLcode res = curl_easy_perform(curl);
                if (res != CURLE_OK) {
                    spdlog::error("InfluxDB connection failed: {}", curl_easy_strerror(res));
                } else {
                    long response_code;
                    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response_code);
                    if (response_code != 204) {
                        spdlog::warn("InfluxDB returned error code: {}", response_code);
                    }
                }
            }
        }
        curl_easy_cleanup(curl);
    }

    static size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
        return size * nmemb;
    }

    // send_request is no longer needed as logic is moved to worker_loop

};

/**
 * @class db_stream
 * @brief A wrapper class for managing an InfluxDB database stream using raw sockets and Line Protocol.
 */
class db_stream
{
  public:
    db_stream(const std::string &influxdb_address)
    {
        std::string host;
        int port;
        std::string db_name;
        parse_url(influxdb_address, host, port, db_name);
        writer_ = std::make_unique<AsyncInfluxDBWriter>(host, port, db_name);
    }

    ~db_stream()
    {
        if (!buffer_.empty()) {
            flush();
        }
        // writer_ destructor will stop the thread
    }

    db_stream(const db_stream &) = delete;
    db_stream &operator=(const db_stream &) = delete;
    
    db_stream(db_stream &&other) noexcept
        : writer_(std::move(other.writer_)), buffer_(std::move(other.buffer_)), 
          batch_size_(other.batch_size_), current_batch_count_(other.current_batch_count_)
    {
    }

    db_stream &operator=(db_stream &&other) noexcept
    {
        if (this != &other)
        {
            writer_ = std::move(other.writer_);
            buffer_ = std::move(other.buffer_);
            batch_size_ = other.batch_size_;
            current_batch_count_ = other.current_batch_count_;
        }
        return *this;
    }

    void set_buffer_size(const size_t size)
    {
        batch_size_ = size;
    }

    size_t get_buffer_size() const
    {
        return batch_size_;
    }

    void flush()
    {
        if (buffer_.empty()) return;
        if (writer_) {
            writer_->push(std::move(buffer_));
        }
        buffer_.clear();
        current_batch_count_ = 0;
    }

    void write_line(const std::string& line)
    {
        if (!buffer_.empty()) {
            buffer_ += "\n";
        }
        buffer_ += line;
        current_batch_count_++;

        if (current_batch_count_ >= batch_size_) {
            flush();
        }
    }

    template <typename T> db_stream &operator<<(T);

  private:
    std::unique_ptr<AsyncInfluxDBWriter> writer_;
    std::string buffer_;
    size_t batch_size_ = 1;
    size_t current_batch_count_ = 0;

    void parse_url(const std::string& url, std::string& host, int& port, std::string& db_name) {
        size_t protocol_pos = url.find("://");
        std::string rest = (protocol_pos == std::string::npos) ? url : url.substr(protocol_pos + 3);
        
        size_t port_pos = rest.find(":");
        size_t query_pos = rest.find("?");
        
        if (port_pos != std::string::npos) {
            host = rest.substr(0, port_pos);
            size_t end_port = (query_pos == std::string::npos) ? rest.length() : query_pos;
            port = std::stoi(rest.substr(port_pos + 1, end_port - port_pos - 1));
        } else {
            host = rest.substr(0, query_pos);
            port = 8086;
        }

        if (query_pos != std::string::npos) {
            std::string query = rest.substr(query_pos + 1);
            if (query.starts_with("db=")) {
                db_name = query.substr(3);
            }
        }
    }
};
} // namespace rt_monitor