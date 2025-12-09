#include <atomic>
#include <condition_variable>
#include <csignal>
#include <mutex>
#include <spdlog/spdlog.h>

namespace rt_monitor
{
class pause_manager
{
  private:
    struct pause_manager_
    {
        std::atomic<bool> paused{true};
        std::atomic<bool> stopped{false};
        std::mutex pause_mutex;
        std::condition_variable pause_cv;
    };

    static pause_manager_ singleton_;

  public:
    static void pause()
    {
        spdlog::trace("pausing monitoring");
        singleton_.paused = true;
    }

    static void resume()
    {
        spdlog::trace("resuming monitoring");
        {
            std::lock_guard<std::mutex> lock(pause_manager::mutex());
            singleton_.paused = false;
        }
        condition_variable().notify_all();
    }

    static void stop()
    {
        spdlog::trace("stopping monitoring");
        singleton_.stopped = true;
    }

    static const auto &stopped()
    {
        return singleton_.stopped;
    }

    static const auto &paused()
    {
        return singleton_.paused;
    }

    static std::mutex &mutex()
    {
        return singleton_.pause_mutex;
    }

    static std::condition_variable &condition_variable()
    {
        return singleton_.pause_cv;
    }
};
} // namespace rt_monitor