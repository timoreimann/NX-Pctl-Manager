// NX-Pctl-Manager — read-only play-timer runtime probe.
// Copyright (C) 2026 Timo Reimann. GPL-3.0-or-later; see repository LICENSE.
#include <switch.h>

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#define INNER_HEAP_SIZE 0x20000
#define POLL_INTERVAL_NS 5000000000LL
#define PROGRAM_ID UINT64_C(0x4200000000F04354)

u32 __nx_applet_type = AppletType_None;
u32 __nx_fs_num_sessions = 1;

static u8 inner_heap[INNER_HEAP_SIZE];
static bool pctl_ready;
static bool pgl_ready;

void __libnx_initheap(void)
{
    extern void *fake_heap_start;
    extern void *fake_heap_end;

    fake_heap_start = inner_heap;
    fake_heap_end = inner_heap + sizeof(inner_heap);
}

static void wait_for_system_version(void)
{
    for (;;) {
        Result rc = setsysInitialize();
        if (R_SUCCEEDED(rc)) {
            SetSysFirmwareVersion version;
            rc = setsysGetFirmwareVersion(&version);
            setsysExit();
            if (R_SUCCEEDED(rc)) {
                hosversionSet(MAKEHOSVERSION(version.major, version.minor, version.micro));
                return;
            }
        }
        svcSleepThread(1000000000LL);
    }
}

static void wait_for_sd_card(void)
{
    for (;;) {
        Result rc = fsInitialize();
        if (R_SUCCEEDED(rc)) {
            rc = fsdevMountSdmc();
            if (R_SUCCEEDED(rc)) return;
            fsExit();
        }
        svcSleepThread(1000000000LL);
    }
}

static void wait_for_time_service(void)
{
    while (R_FAILED(timeInitialize()))
        svcSleepThread(1000000000LL);
}

void __appInit(void)
{
    while (R_FAILED(smInitialize()))
        svcSleepThread(1000000000LL);

    wait_for_system_version();
    wait_for_sd_card();
    wait_for_time_service();
}

void __appExit(void)
{
    if (pctl_ready) pctlExit();
    if (pgl_ready) pglExit();
    timeExit();
    fsdevUnmountAll();
    fsExit();
    smExit();
}

static Result format_timestamp(char *out, size_t out_size,
    TimeCalendarAdditionalInfo *additional, bool for_filename)
{
    u64 posix_time = 0;
    TimeCalendarTime calendar;
    Result rc = timeGetCurrentTime(TimeType_UserSystemClock, &posix_time);
    if (R_FAILED(rc)) return rc;

    rc = timeToCalendarTimeWithMyRule(posix_time, &calendar, additional);
    if (R_FAILED(rc)) return rc;

    if (for_filename) {
        snprintf(out, out_size, "%04u%02u%02u_%02u%02u%02u",
            calendar.year, calendar.month, calendar.day,
            calendar.hour, calendar.minute, calendar.second);
    } else {
        snprintf(out, out_size, "%04u-%02u-%02uT%02u:%02u:%02u",
            calendar.year, calendar.month, calendar.day,
            calendar.hour, calendar.minute, calendar.second);
    }
    return 0;
}

static FILE *open_log(char *path, size_t path_size)
{
    char timestamp[32];
    TimeCalendarAdditionalInfo additional;

    while (R_FAILED(format_timestamp(timestamp, sizeof(timestamp), &additional, true)))
        svcSleepThread(1000000000LL);

    if (mkdir("sdmc:/switch", 0777) != 0 && errno != EEXIST)
        return NULL;

    snprintf(path, path_size, "sdmc:/switch/nx_pctl_runtime_%s.log", timestamp);
    return fopen(path, "a");
}

static Result ensure_pctl(void)
{
    if (pctl_ready) return 0;
    Result rc = pctlInitialize();
    if (R_SUCCEEDED(rc)) pctl_ready = true;
    return rc;
}

static Result ensure_pgl(void)
{
    if (pgl_ready) return 0;
    Result rc = pglInitialize();
    if (R_SUCCEEDED(rc)) pgl_ready = true;
    return rc;
}

static void write_sample(FILE *log, u64 sequence)
{
    char timestamp[32] = "unavailable";
    TimeCalendarAdditionalInfo additional;
    memset(&additional, 0, sizeof(additional));
    Result time_rc = format_timestamp(timestamp, sizeof(timestamp), &additional, false);

    u64 application_pid = 0;
    Result pgl_rc = ensure_pgl();
    if (R_SUCCEEDED(pgl_rc))
        pgl_rc = pglGetApplicationProcessId(&application_pid);

    bool enabled = false;
    bool restricted = false;
    u64 remaining = 0;
    u64 spent = 0;
    Result pctl_rc = ensure_pctl();
    Result rc1453 = pctl_rc;
    Result rc1454 = pctl_rc;
    Result rc1455 = pctl_rc;
    Result rc1952 = pctl_rc;

    if (R_SUCCEEDED(pctl_rc)) {
        Service *service = pctlGetServiceSession_Service();
        rc1453 = serviceDispatchOut(service, 1453, enabled);
        rc1454 = serviceDispatchOut(service, 1454, remaining);
        rc1455 = serviceDispatchOut(service, 1455, restricted);
        rc1952 = serviceDispatchOut(service, 1952, spent);
    }

    fprintf(log,
        "sample=%llu time=%s time_rc=0x%08X tz=%.8s utc_offset=%d "
        "application_query_rc=0x%08X application_process_present=%u application_pid=0x%016llX "
        "pctl_init_rc=0x%08X "
        "1453_rc=0x%08X enabled=%u "
        "1454_rc=0x%08X remaining_raw=0x%016llX remaining_dec=%llu "
        "1455_rc=0x%08X restricted=%u "
        "1952_rc=0x%08X spent_raw=0x%016llX spent_dec=%llu\n",
        (unsigned long long)sequence, timestamp, (unsigned)time_rc,
        additional.timezoneName, additional.offset,
        (unsigned)pgl_rc,
        (unsigned)(R_SUCCEEDED(pgl_rc) && application_pid != 0),
        (unsigned long long)application_pid, (unsigned)pctl_rc,
        (unsigned)rc1453, (unsigned)enabled,
        (unsigned)rc1454, (unsigned long long)remaining,
        (unsigned long long)remaining,
        (unsigned)rc1455, (unsigned)restricted,
        (unsigned)rc1952, (unsigned long long)spent,
        (unsigned long long)spent);
    fflush(log);
}

int main(void)
{
    char path[128];
    FILE *log = NULL;
    while (log == NULL) {
        log = open_log(path, sizeof(path));
        if (log == NULL) svcSleepThread(POLL_INTERVAL_NS);
    }

    u32 version = hosversionGet();
    fprintf(log,
        "nx_pctl_runtime_probe program_id=0x%016llX hos=%u.%u.%u "
        "poll_interval_seconds=5 pctl_mode=read_only "
        "application_process_present_does_not_prove_visual_foreground=true\n",
        (unsigned long long)PROGRAM_ID,
        HOSVER_MAJOR(version), HOSVER_MINOR(version), HOSVER_MICRO(version));
    fflush(log);

    for (u64 sequence = 0;; sequence++) {
        write_sample(log, sequence);
        svcSleepThread(POLL_INTERVAL_NS);
    }
}
