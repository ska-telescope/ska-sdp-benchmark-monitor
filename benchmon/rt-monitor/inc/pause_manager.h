#include <atomic>
#include <condition_variable>
#include <csignal>
#include <mutex>
#include <spdlog/spdlog.h>

namespace rt_monitor
{
/**
 * @file pause_manager.h
 * @brief Defines the pause_manager class for controlling pause and stop states in monitoring.
 *
 * The pause_manager class provides static methods to control and query the paused and stopped
 * states of a monitoring process. It uses atomic flags for thread-safe state management,
 * and provides access to a mutex and condition variable for synchronization between threads.
 *
 * Usage:
 * - Call pause_manager::pause() to pause monitoring.
 * - Call pause_manager::resume() to resume monitoring.
 * - Call pause_manager::stop() to stop monitoring.
 * - Use pause_manager::paused() and pause_manager::stopped() to query current states.
 * - Use pause_manager::mutex() and pause_manager::condition_variable() for thread synchronization.
 *
 * Thread Safety:
 * All state changes are thread-safe due to the use of atomic variables and synchronization primitives.
 *
 * Logging:
 * Each state change logs a trace message using spdlog.
 */
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
        condition_variable().notify_all();
    }

    static const std::atomic<bool> &stopped()
    {
        return singleton_.stopped;
    }

    static const std::atomic<bool> &paused()
    {
        return singleton_.paused;
    }

    static void wait_if_paused()
    {
        if (paused())
        {
            spdlog::trace("monitoring paused, waiting...");
            std::unique_lock<std::mutex> lock(mutex());
            condition_variable().wait(lock, [] { return !paused().load() || stopped().load(); });
            spdlog::trace("monitoring resumed or stopped");
        }
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