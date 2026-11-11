#include "api.h"
#include "config.h"
#include "certs.h"
#include <Arduino.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// nextResetTime is a 13-digit epoch-milliseconds integer. Converting it with
// an int-typed default ("variant | 0") routes through 32-bit int and wraps
// modulo 2^32 — that turned 2026-10-17 into 1970-01-15 on the live stick.
// Must convert as 64-bit BEFORE dividing down to seconds.
static uint32_t resetEpochSec(JsonObject lim) {
    JsonVariant v = lim["nextResetTime"];
    if (v.is<uint64_t>()) return (uint32_t)(v.as<uint64_t>() / 1000ULL);
    if (v.is<int64_t>())  return (uint32_t)((uint64_t)v.as<int64_t>() / 1000ULL);
    return 0;
}

// GET {QUOTA_LIMIT_ENDPOINT} with the raw Coding-Plan API key in the
// Authorization header (no "Bearer " prefix — the official zai-coding-plugins
// usage-query script sends it bare, and the endpoint accepts it that way).
//
// data.limits[] entries carry (unit, number) window descriptors:
//   TOKENS_LIMIT unit=3 number=5 → rolling 5-hour token quota  → h5
//   TOKENS_LIMIT unit=6 number=1 → weekly token quota          → d7
//   TIME_LIMIT   unit=5 number=1 → monthly MCP/tool quota      → mcp*
// percentage is a plain 0-100 integer; nextResetTime is epoch milliseconds.
bool fetchUsage(const char* token, UsageData& out) {
    out.mcpPct = -1;
    out.mcpUsed = out.mcpTotal = 0;
    out.mcpResetEpoch = 0;
    out.level[0] = '\0';

    WiFiClientSecure client;
    client.setCACert(CA_BUNDLE);

    HTTPClient https;
    if (!https.begin(client, QUOTA_LIMIT_ENDPOINT)) {
        strlcpy(out.error, "https_init", sizeof(out.error));
        out.ok = false;
        return false;
    }

    https.addHeader("Authorization", token);
    https.addHeader("Accept", "application/json");
    https.setTimeout(API_TIMEOUT_MS);

    Serial.printf("[API] GET %s\n", QUOTA_LIMIT_ENDPOINT);
    int code = https.GET();
    Serial.printf("[API] HTTP %d\n", code);

    if (code <= 0) {
        snprintf(out.error, sizeof(out.error), "http_%d", code);
        out.ok = false;
        https.end();
        return false;
    }

    String body = https.getString();
    https.end();

    if (code != 200) {
        if (code == 401) strlcpy(out.error, "auth_failed", sizeof(out.error));
        else snprintf(out.error, sizeof(out.error), "http_%d", code);
        out.ok = false;
        return false;
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
        strlcpy(out.error, "bad_json", sizeof(out.error));
        out.ok = false;
        return false;
    }

    bool gotH5 = false, gotWk = false;
    JsonArray limits = doc["data"]["limits"].as<JsonArray>();
    if (limits.isNull()) {
        strlcpy(out.error, "no_limits", sizeof(out.error));
        out.ok = false;
        return false;
    }

    for (JsonObject lim : limits) {
        const char* type = lim["type"] | "";
        int unit = lim["unit"] | -1;
        int number = lim["number"] | -1;
        // Zhipu's unit enum observed live: 3=hours, 5=months, 6=weeks. Match
        // on unit first; number (window length) disambiguates if it shifts.
        bool is5h  = strcmp(type, "TOKENS_LIMIT") == 0 &&
                     (unit == 3 || number == 5);
        bool isWk  = strcmp(type, "TOKENS_LIMIT") == 0 && !is5h;
        bool isMcp = strcmp(type, "TIME_LIMIT") == 0;

        if (is5h && !gotH5) {
            out.h5 = lim["percentage"] | 0;
            out.h5ResetEpoch = resetEpochSec(lim);
            gotH5 = true;
        } else if (isWk && !gotWk) {
            out.d7 = lim["percentage"] | 0;
            out.d7ResetEpoch = resetEpochSec(lim);
            gotWk = true;
        } else if (isMcp && out.mcpPct < 0) {
            out.mcpPct   = lim["percentage"] | -1;
            out.mcpUsed  = lim["currentValue"] | 0;
            out.mcpTotal = lim["usage"] | 0;
            out.mcpResetEpoch = resetEpochSec(lim);
        }
    }

    // Plan tier, e.g. "lite"/"max" — shown on the flame screen
    strlcpy(out.level, doc["data"]["level"] | "", sizeof(out.level));

    Serial.printf("[API] 5h: %.0f%%  wk: %.0f%%  mcp: %d%%  level: %s\n",
                  gotH5 ? out.h5 : -1.0f, gotWk ? out.d7 : -1.0f, out.mcpPct, out.level);

    if (!gotH5 && !gotWk) {
        strlcpy(out.error, "no_quota_data", sizeof(out.error));
        out.ok = false;
        return false;
    }
    if (!gotH5) out.h5 = 0;
    if (!gotWk) out.d7 = 0;

    out.ok = true;
    return true;
}
