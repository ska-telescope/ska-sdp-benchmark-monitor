#pragma once
#include <string>
#include <vector>
#include <sstream>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>
#include <spdlog/spdlog.h>
#include <cstring>
#include <iostream>
#include <thread>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <memory>

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
    int sock_ = -1;
    std::thread worker_;
    std::queue<std::string> queue_;
    std::mutex mutex_;
    std::condition_variable cv_;
    bool running_;

    void worker_loop() {
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
                send_request(payload);
            }
        }
        if (sock_ != -1) close(sock_);
    }

    void connect_to_server() {
        struct hostent *server = gethostbyname(host_.c_str());
        if (server == nullptr) {
            spdlog::error("No such host: {}", host_);
            return;
        }

        sock_ = socket(AF_INET, SOCK_STREAM, 0);
        if (sock_ < 0) {
            spdlog::error("Error opening socket");
            return;
        }

        struct sockaddr_in serv_addr;
        std::memset(&serv_addr, 0, sizeof(serv_addr));
        serv_addr.sin_family = AF_INET;
        std::memcpy(&serv_addr.sin_addr.s_addr, server->h_addr, server->h_length);
        serv_addr.sin_port = htons(port_);

        if (connect(sock_, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
            spdlog::error("Error connecting to InfluxDB");
            close(sock_);
            sock_ = -1;
        }
    }

    void send_request(const std::string& data) {
        if (sock_ < 0) {
            connect_to_server();
            if (sock_ < 0) return;
        }

        std::stringstream request;
        request << "POST /write?db=" << db_name_ << " HTTP/1.1\r\n";
        request << "Host: " << host_ << ":" << port_ << "\r\n";
        request << "Content-Length: " << data.length() << "\r\n";
        request << "Content-Type: text/plain\r\n";
        request << "Connection: Keep-Alive\r\n";
        request << "\r\n";
        request << data;

        std::string req_str = request.str();
        ssize_t total_sent = 0;
        while (total_sent < req_str.length()) {
            ssize_t sent = send(sock_, req_str.c_str() + total_sent, req_str.length() - total_sent, MSG_NOSIGNAL);
            if (sent < 0) {
                spdlog::error("Error sending data to InfluxDB, reconnecting...");
                close(sock_);
                sock_ = -1;
                // Retry once
                connect_to_server();
                if (sock_ >= 0) {
                    total_sent = 0; // Restart sending
                    continue;
                } else {
                    return; // Give up
                }
            }
            total_sent += sent;
        }
        
        char resp_buffer[4096];
        ssize_t valread = read(sock_, resp_buffer, sizeof(resp_buffer) - 1);
        if (valread <= 0) {
             close(sock_);
             sock_ = -1;
        } else {
             resp_buffer[valread] = '\0';
             std::string resp(resp_buffer);
             if (resp.find("204 No Content") == std::string::npos) {
                 spdlog::warn("InfluxDB returned unexpected response: {}", resp.substr(0, std::min(resp.length(), (size_t)100)));
             }
        }
    }
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