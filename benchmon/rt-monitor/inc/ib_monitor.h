#pragma once
#include <string>
#include <vector>

namespace rt_monitor::ib
{
    template <typename Stream>
    void start_sampling(double interval_ms, Stream &&stream);
}
