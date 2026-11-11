<div align="center">

# GLM Usage Stick

**Your [Zhipu GLM Coding Plan](https://open.bigmodel.cn) quota, glanceable on a tiny ESP32 stick — with a campfire that burns down as you spend it.**

Fork of the wonderful [oauramos/claude-usage-stick](https://github.com/oauramos/claude-usage-stick) (MIT), re-targeted from Anthropic rate-limit headers to Zhipu's `open.bigmodel.cn` usage endpoints. Flame art baked from [patch-gg/pixelfx](https://github.com/patch-gg/pixelfx) (MIT).

</div>

---

A standalone desk gadget that polls the same usage endpoint the official `zai-coding-plugins` `glm-plan-usage` tool calls, and shows how much of your Coding Plan is left — no computer, no app, no cloud. Flash it, and it just sits there telling you how much runway you have left.

## What it does

**Dashboard** — the 5-hour and weekly token windows as live bars, reset countdowns with absolute reset clocks, the monthly MCP/tool quota, and your plan tier — refreshed every 30 s – 5 min.

**Flame screen** — a pixel-art campfire (baked from pixelfx's `fire/campfire`) where **the fire is the fuel you have left**:

- flame **height** tracks the 5-hour window remaining — burn tokens and the fire sinks toward its logs
- flame **color** shifts continuously as quota is spent: platinum → gold → lava-orange → ember-red → dying coals
- in the last 10 minutes before the 5h window resets, the fire visibly *gathers itself* (pulses toward white) — then flares back up on reset
- the weekly window and MCP quota ride along as text

**Portrait flame** — hold A to switch to a vertical, full-screen, *text-free* fire anchored on the USB edge: quota told purely by color and height. A desk ambiance light that happens to be a meter.

## Controls (T-Display S3 build)

| Gesture | Action |
| --- | --- |
| A short press | brightness (4 levels) |
| A hold ≥ 600 ms | dashboard → landscape flame → portrait flame → … |
| B | force a refresh |

## How it works

Every poll cycle the stick does a plain HTTPS GET:

```
GET https://open.bigmodel.cn/api/monitor/usage/quota/limit
Authorization: <your Zhipu API key, raw — no Bearer prefix>
```

and reads `data.limits[]`: `TOKENS_LIMIT unit=3` (rolling 5-hour window), `unit=6` (weekly), `TIME_LIMIT` (monthly MCP/tool quota), plus `data.level` (plan tier). That's the same request shape the official plugin makes; Zhipu never sees anything but a normal API client.

TLS is pinned to the serving chain's stable anchors (WoTrus intermediate / Sectigo R46 / USERTrust root — see `src/certs.cpp`). Zhipu rotated their CA in October 2026, which silently broke every stick pinned to the old TrustAsia chain; this build re-pins to the new one with three anchors so a leaf or intermediate rotation won't kill it again. Rotation captures live in the project wiki of the original author.

## Getting one running

```bash
git clone https://github.com/caoruidong-1979/glm-usage-stick.git
cd glm-usage-stick
pio run -e tdisplay-s3-glm -t upload
```

Needs the [PlatformIO CLI](https://platformio.org/install/cli). The primary target is the LilyGo T-Display S3 (16 MB); other upstream board envs still build but are untested with the GLM endpoints.

Without `src/config_secret.h` (see below) the device opens a WiFi provisioning portal on first boot: set your WiFi and paste your API key from your phone. The key is AES-256-GCM encrypted on-device flash.

### Headless personal build

Copy `src/config_secret.example.h` to `src/config_secret.h`, fill in your WiFi and API key, and the `NO_PIN_LOCK` build self-provisions on first boot — no portal, no PIN. **`config_secret.h` is git-ignored; never commit a real key.**

### Re-baking the flame

The fire frames are generated, not hand-drawn:

```bash
git clone https://github.com/patch-gg/pixelfx.git   # next to this repo
cd pixelfx && node tools/render.mjs fire/campfire --sheet
cd ../glm-usage-stick && python tools/bake_flame.py
```

`bake_flame.py` quantizes the sprite sheet to a 20-color master palette (the 9-entry fire ramp stays remappable at runtime — that's how the color follows quota without re-baking), crops and upscales two variants (160×160 landscape, 170×216 portrait) and emits `src/flame_frames.*` plus preview PNGs in `tools/previews/`.

## Security notes

- The API key is stored AES-256-GCM encrypted in NVS; the PIN never persists (upstream design, kept intact). The personal `NO_PIN_LOCK` build bakes credentials into the image instead — anyone with the flash image could extract them, that's the trade.
- TLS certificate pinning, not trust-on-first-use: a hostile network can't silently re-point the stick.
- No telemetry, no cloud, no outbound traffic besides the one polling endpoint (plus NTP).

## Credits

- [oauramos/claude-usage-stick](https://github.com/oauramos/claude-usage-stick) — the entire device: hardware support, crypto, captive portal, UI framework. MIT.
- [patch-gg/pixelfx](https://github.com/patch-gg/pixelfx) — the campfire effect the flame screens are baked from. MIT.
- [zai-org/zai-coding-plugins](https://github.com/zai-org/zai-coding-plugins) — the documented usage-query request shape.

## License

MIT — see [LICENSE](LICENSE). Flame frames generated from MIT-licensed pixelfx effects are re-distributed under the same terms.
