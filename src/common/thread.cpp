// Copyright 2013 Dolphin Emulator Project / 2014 Citra Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

#include <algorithm>
#include <fstream>
#include <string>
#include <vector>

#include "common/error.h"
#include "common/logging/log.h"
#include "common/thread.h"
#ifdef __APPLE__
#include <mach/mach.h>
#elif defined(_WIN32)
#include <windows.h>
#include "common/string_util.h"
#else
#if defined(__Bitrig__) || defined(__DragonFly__) || defined(__FreeBSD__) || defined(__OpenBSD__)
#include <pthread_np.h>
#else
#include <pthread.h>
#endif
#include <sched.h>
#endif
#ifndef _WIN32
#include <unistd.h>
#endif
#ifdef __linux__
#include <sys/resource.h>
#include <sys/syscall.h>
#endif

#ifdef __FreeBSD__
#define cpu_set_t cpuset_t
#endif

namespace Common {

#ifdef _WIN32

void SetCurrentThreadPriority(ThreadPriority new_priority) {
    auto handle = GetCurrentThread();
    int windows_priority = 0;
    switch (new_priority) {
    case ThreadPriority::Low:
        windows_priority = THREAD_PRIORITY_BELOW_NORMAL;
        break;
    case ThreadPriority::Normal:
        windows_priority = THREAD_PRIORITY_NORMAL;
        break;
    case ThreadPriority::High:
        windows_priority = THREAD_PRIORITY_ABOVE_NORMAL;
        break;
    case ThreadPriority::VeryHigh:
        windows_priority = THREAD_PRIORITY_HIGHEST;
        break;
    case ThreadPriority::Critical:
        windows_priority = THREAD_PRIORITY_TIME_CRITICAL;
        break;
    default:
        windows_priority = THREAD_PRIORITY_NORMAL;
        break;
    }
    SetThreadPriority(handle, windows_priority);
}

#else

void SetCurrentThreadPriority(ThreadPriority new_priority) {
    pthread_t this_thread = pthread_self();

    const auto scheduling_type = SCHED_OTHER;
    s32 max_prio = sched_get_priority_max(scheduling_type);
    s32 min_prio = sched_get_priority_min(scheduling_type);
    u32 level = std::max(static_cast<u32>(new_priority) + 1, 4U);

    struct sched_param params;
    if (max_prio > min_prio) {
        params.sched_priority = min_prio + ((max_prio - min_prio) * level) / 4;
    } else {
        params.sched_priority = min_prio - ((min_prio - max_prio) * level) / 4;
    }

    pthread_setschedparam(this_thread, scheduling_type, &params);
}

#endif

#ifdef _MSC_VER

// Sets the debugger-visible name of the current thread.
void SetCurrentThreadName(const char* name) {
    SetThreadDescription(GetCurrentThread(), UTF8ToUTF16W(name).data());
}

#else // !MSVC_VER, so must be POSIX threads

// MinGW with the POSIX threading model does not support pthread_setname_np
#if !defined(_WIN32) || defined(_MSC_VER)
void SetCurrentThreadName(const char* name) {
#ifdef __APPLE__
    pthread_setname_np(name);
#elif defined(__Bitrig__) || defined(__DragonFly__) || defined(__FreeBSD__) || defined(__OpenBSD__)
    pthread_set_name_np(pthread_self(), name);
#elif defined(__NetBSD__)
    pthread_setname_np(pthread_self(), "%s", (void*)name);
#elif defined(__linux__)
    // Linux limits thread names to 15 characters and will outright reject any
    // attempt to set a longer name with ERANGE.
    std::string truncated(name, std::min(strlen(name), static_cast<std::size_t>(15)));
    if (int e = pthread_setname_np(pthread_self(), truncated.c_str())) {
        errno = e;
        LOG_ERROR(Common, "Failed to set thread name to '{}': {}", truncated, GetLastErrorMsg());
    }
#else
    pthread_setname_np(pthread_self(), name);
#endif
}
#endif

#if defined(_WIN32)
void SetCurrentThreadName(const char*) {
    // Do Nothing on MingW
}
#endif

#endif

#ifdef __linux__

namespace {

// Reads a single integer from a sysfs node, returning -1 if it is missing or unreadable.
long ReadSysfsLong(const std::string& path) {
    std::ifstream file(path);
    long value = -1;
    if (!file || !(file >> value)) {
        return -1;
    }
    return value;
}

// Returns one "capacity" figure per CPU. Prefers the kernel's normalized cpu_capacity, falls back
// to the maximum cpufreq frequency, and returns an empty vector if neither is available.
std::vector<long> GetCpuCapacities() {
    const long count = sysconf(_SC_NPROCESSORS_CONF);
    if (count <= 1) {
        return {};
    }
    std::vector<long> capacities(static_cast<std::size_t>(count), -1);
    bool any = false;
    for (long cpu = 0; cpu < count; ++cpu) {
        capacities[cpu] =
            ReadSysfsLong("/sys/devices/system/cpu/cpu" + std::to_string(cpu) + "/cpu_capacity");
        any |= capacities[cpu] > 0;
    }
    if (!any) {
        for (long cpu = 0; cpu < count; ++cpu) {
            capacities[cpu] = ReadSysfsLong("/sys/devices/system/cpu/cpu" + std::to_string(cpu) +
                                            "/cpufreq/cpuinfo_max_freq");
            any |= capacities[cpu] > 0;
        }
    }
    return any ? capacities : std::vector<long>{};
}

} // Anonymous namespace

int PinCurrentThreadToPerformanceCores() {
    const auto capacities = GetCpuCapacities();
    if (capacities.empty()) {
        return 0;
    }
    const long max_capacity = *std::max_element(capacities.begin(), capacities.end());
    cpu_set_t set;
    CPU_ZERO(&set);
    int selected = 0;
    for (std::size_t cpu = 0; cpu < capacities.size(); ++cpu) {
        if (capacities[cpu] == max_capacity) {
            CPU_SET(cpu, &set);
            ++selected;
        }
    }
    // Homogeneous CPU (or every core is "big"): leave the scheduler alone.
    if (selected == 0 || static_cast<std::size_t>(selected) == capacities.size()) {
        return 0;
    }
    if (sched_setaffinity(0, sizeof(set), &set) != 0) {
        LOG_WARNING(Common, "sched_setaffinity failed: {}", Common::GetLastErrorMsg());
        return 0;
    }
    return selected;
}

bool RaiseCurrentThreadPriority() {
    // -8 matches Android's THREAD_PRIORITY_URGENT_DISPLAY, which app processes are allowed to
    // set for their own threads.
    constexpr int target_nice = -8;
    const auto tid = static_cast<id_t>(syscall(SYS_gettid));
    if (setpriority(PRIO_PROCESS, tid, target_nice) != 0) {
        LOG_WARNING(Common, "setpriority failed: {}", Common::GetLastErrorMsg());
        return false;
    }
    return true;
}

#else

int PinCurrentThreadToPerformanceCores() {
    return 0;
}

bool RaiseCurrentThreadPriority() {
    return false;
}

#endif

} // namespace Common
