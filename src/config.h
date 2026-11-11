#pragma once

// ── Firmware version ─────────────────────────────────────
#define FW_VERSION              "1.0.0-zhipu"  // shown on the boot screen

// ── Polling ──────────────────────────────────────────────
#define DEFAULT_POLL_SEC        120
#define MIN_POLL_SEC            30
#define MAX_POLL_SEC            300

// ── Security ─────────────────────────────────────────────
#define MAX_PIN_ATTEMPTS        10
#define LOCKOUT_BASE_SEC        60       // doubles each failure
#define KDF_ROUNDS              10000

// ── Display ──────────────────────────────────────────────
#ifdef BOARD_ESP32C3_OLED
  #define SCREEN_W              72
  #define SCREEN_H              40
  // No SCREEN_ROT — U8g2 uses U8G2_R0
#elif defined(BOARD_TDISPLAY_S3)
  #define SCREEN_W              320
  #define SCREEN_H              170
  #define SCREEN_ROT            1
#elif defined(BOARD_TDISPLAY_S3_AMOLED)
  #define SCREEN_W              536
  #define SCREEN_H              240
  #define SCREEN_ROT            0
#elif defined(BOARD_TDISPLAY_ESP32)
  #define SCREEN_W              240
  #define SCREEN_H              135
  #define SCREEN_ROT            3
#elif defined(BOARD_T8_S2)
  #define SCREEN_W              240
  #define SCREEN_H              135
  #define SCREEN_ROT            3
#elif defined(BOARD_CROWPANEL_ADV_35)
  #define SCREEN_W              480
  #define SCREEN_H              320
  #define SCREEN_ROT            3
#else
  #define SCREEN_W              240
  #define SCREEN_H              135
  #define SCREEN_ROT            3
#endif
#define DEFAULT_BRIGHTNESS      2        // 0=off 1=dim 2=normal 3=bright

// ── Network ──────────────────────────────────────────────
#define WIFI_CONNECT_TIMEOUT_S  20
#define API_TIMEOUT_MS          15000
// Zhipu GLM Coding Plan quota monitor (same endpoint family the official
// zai-coding-plugins usage-query script calls). Auth: raw API key in the
// Authorization header. NVS namespace kept as "claude" so a Claude-stick
// reflash keeps its stored settings layout.
#define QUOTA_LIMIT_ENDPOINT    "https://open.bigmodel.cn/api/monitor/usage/quota/limit"
// status.anthropic.com redirects here — query the canonical host directly
#define STATUS_ENDPOINT         "https://status.claude.com/api/v2/incidents/unresolved.json"

// ── Anthropic news feed (T-Display S3 news screen) ───────
// Streamed and abandoned after the first NEWS_MAX_ITEMS items — the full feed
// is ~200KB but each item is tiny.
#define NEWS_FEED_URL           "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml"
#define NEWS_POLL_SEC           21600    // refetch every 6h
#define NEWS_RETRY_SEC          1800     // failed fetch retries in 30min
#define NEWS_MAX_ITEMS          5
#define NEWS_TIMEOUT_MS         10000

// ── NVS ──────────────────────────────────────────────────
#define NVS_NAMESPACE           "claude"

// ── Headless build (-DNO_PIN_LOCK) ───────────────────────
// Personal-device convenience: credentials baked in at compile time. First
// boot self-provisions silently (no AP portal, no button PIN entry) — the
// token is still AES-encrypted at rest, but with this compile-time default
// PIN that unlockPhase applies automatically. Anyone with the flash image
// could extract these anyway, so this only drops the physical-access gate.
//
// Credentials live in src/config_secret.h — git-ignored on purpose (copy
// config_secret.example.h to create yours). Without that file the firmware
// still builds; the device opens the normal WiFi provisioning portal on
// first boot instead. NEVER put a real API key in a committed file.
#ifdef NO_PIN_LOCK
#define DEFAULT_PIN             "0000"
#if __has_include("config_secret.h")
#include "config_secret.h"      // defines BUILD_SSID / BUILD_WIFIPASS / BUILD_TOKEN
#endif
#endif

// ── Feature flags (set via build_flags in platformio.ini) ────
// MANGO_UI — the "Mango" dashboard: model-status mascots from status.claude.com,
//   battery + WiFi-signal icons in the header, dashboard-styled PIN screen, and
//   Button A = flip screen / Button B = brightness. Enabled on the boards whose
//   panels have the vertical room for it: BOARD_TDISPLAY_S3 (320x170) and
//   BOARD_M5STICK_C_PLUS (240x135). Mango-specific geometry branches on the board.
