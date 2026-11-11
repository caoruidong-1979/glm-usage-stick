#pragma once
#include <stdint.h>

// Zhipu GLM Coding Plan quotas, mapped onto the stick's two bars:
//   h5  — TOKENS_LIMIT unit=3 (rolling 5-hour token quota)
//   d7  — TOKENS_LIMIT unit=6 (weekly token quota)
// plus the monthly MCP/tool quota as a bonus line when present.
struct UsageData {
    float    h5;
    float    d7;
    uint32_t h5ResetEpoch;
    uint32_t d7ResetEpoch;
    bool     ok;
    char     error[64];
    int      mcpPct;          // TIME_LIMIT percentage, -1 when absent
    int      mcpUsed;
    int      mcpTotal;
    uint32_t mcpResetEpoch;
    char     level[12];       // plan tier, e.g. "max" (empty when absent)
};

bool fetchUsage(const char* token, UsageData& out);
