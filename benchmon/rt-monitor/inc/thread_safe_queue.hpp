#pragma once

#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>

namespace rt_monitor
{

template <typename T>
class ThreadSafeQueue
{
public:
    ThreadSafeQueue() = default;
    ThreadSafeQueue(const ThreadSafeQueue&) = delete;
    ThreadSafeQueue& operator=(const ThreadSafeQueue&) = delete;

    void push(T item)
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            queue_.push(std::move(item));
        }
        cond_var_.notify_one();
    }

    bool pop(T& item)
    {
        std::unique_lock<std::mutex> lock(mutex_);
        cond_var_.wait(lock, [this] { return !queue_.empty() || stop_; });

        if (queue_.empty() && stop_)
        {
            return false;
        }

        item = std::move(queue_.front());
        queue_.pop();
        return true;
    }

    bool pop(T& item, std::chrono::milliseconds timeout)
    {
        std::unique_lock<std::mutex> lock(mutex_);
        if (!cond_var_.wait_for(lock, timeout, [this] { return !queue_.empty() || stop_; }))
        {
            return false;
        }

        if (queue_.empty() && stop_)
        {
            return false;
        }
        
        if (queue_.empty())
        {
            return false;
        }

        item = std::move(queue_.front());
        queue_.pop();
        return true;
    }

    void stop()
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            stop_ = true;
        }
        cond_var_.notify_all();
    }
    
    size_t size() const
    {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.size();
    }

private:
    std::queue<T> queue_;
    mutable std::mutex mutex_;
    std::condition_variable cond_var_;
    bool stop_ = false;
};

} // namespace rt_monitor
