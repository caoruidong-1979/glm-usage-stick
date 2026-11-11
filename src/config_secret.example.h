// Copy this file to src/config_secret.h and fill in your own values.
// config_secret.h is git-ignored: your WiFi password and Zhipu API key
// never leave this machine. With NO_PIN_LOCK builds, these are baked in
// and the device self-provisions on first boot.
//
// The API key is a Zhipu GLM Coding Plan key (https://open.bigmodel.cn)
// — the same key the official zai-coding-plugins usage-query uses.
#define BUILD_SSID              "YourWiFiName"
#define BUILD_WIFIPASS          "YourWiFiPassword"
#define BUILD_TOKEN             "your-zhipu-api-key"
