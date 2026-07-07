"""
浏览器指纹伪装 + Stealth 脚本注入
移植自 anything-analyzer (src/main/fingerprint/ + src/preload/stealth-script.ts)
"""
import random
import math
import json
from dataclasses import dataclass, field


# ════════════════════════════════════════════════════════════════
# 设备预设（对应 presets.ts）
# ════════════════════════════════════════════════════════════════

@dataclass
class DevicePreset:
    platform: str
    oscpu: str
    screens: list[tuple[int, int]]
    dprs: list[float]
    webgl_vendors: list[str]
    webgl_renderers: list[str]
    hardware_concurrencies: list[int]
    device_memories: list[int]
    color_depth: int


CHROME_VERSIONS = ["131.0.0.0", "130.0.0.0", "129.0.0.0", "128.0.0.0", "127.0.0.0"]

WINDOWS_PRESETS = [
    DevicePreset(
        platform="Win32", oscpu="Windows NT 10.0; Win64; x64",
        screens=[(1920, 1080), (2560, 1440), (1366, 768), (1536, 864)],
        dprs=[1, 1.25, 1.5],
        webgl_vendors=["Google Inc. (NVIDIA)"],
        webgl_renderers=[
            "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        ],
        hardware_concurrencies=[4, 8, 12, 16],
        device_memories=[8, 16, 32],
        color_depth=24,
    ),
    DevicePreset(
        platform="Win32", oscpu="Windows NT 10.0; Win64; x64",
        screens=[(1920, 1080), (2560, 1440)],
        dprs=[1, 1.25],
        webgl_vendors=["Google Inc. (Intel)"],
        webgl_renderers=[
            "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "ANGLE (Intel, Intel(R) UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        ],
        hardware_concurrencies=[4, 8, 12],
        device_memories=[8, 16],
        color_depth=24,
    ),
    DevicePreset(
        platform="Win32", oscpu="Windows NT 10.0; Win64; x64",
        screens=[(1920, 1080), (2560, 1440), (3440, 1440)],
        dprs=[1, 1.25, 1.5],
        webgl_vendors=["Google Inc. (AMD)"],
        webgl_renderers=[
            "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        ],
        hardware_concurrencies=[8, 12, 16],
        device_memories=[16, 32],
        color_depth=24,
    ),
]

ALL_PRESETS = WINDOWS_PRESETS  # 只用 Windows（social-publisher 运行环境）

TIMEZONE_LANGUAGES = {
    "Asia/Shanghai": ["zh-CN", "zh", "en"],
    "Asia/Tokyo": ["ja", "en"],
    "Asia/Seoul": ["ko", "en"],
    "America/New_York": ["en-US", "en"],
    "America/Los_Angeles": ["en-US", "en"],
    "Europe/London": ["en-GB", "en"],
    "Europe/Berlin": ["de-DE", "de", "en"],
    "Europe/Paris": ["fr-FR", "fr", "en"],
}

TIMEZONE_OFFSETS = {
    "Asia/Shanghai": -480,
    "Asia/Tokyo": -540,
    "Asia/Seoul": -540,
    "America/New_York": 300,
    "America/Los_Angeles": 480,
    "Europe/London": 0,
    "Europe/Berlin": -60,
    "Europe/Paris": -60,
}


# ════════════════════════════════════════════════════════════════
# 指纹 Profile
# ════════════════════════════════════════════════════════════════

@dataclass
class FingerprintProfile:
    user_agent: str
    platform: str
    oscpu: str
    app_version: str
    screen_width: int
    screen_height: int
    color_depth: int
    device_pixel_ratio: float
    hardware_concurrency: int
    device_memory: int
    webgl_vendor: str
    webgl_renderer: str
    canvas_noise: int
    audio_noise: int
    languages: list[str]
    timezone: str
    timezone_offset: int
    webrtc_policy: str = "block"


def _pick(seq: list) -> any:
    return random.choice(seq)


def _random_seed() -> int:
    return random.randint(0, 0xFFFFFFFF)


def _build_ua(preset: DevicePreset, chrome_version: str) -> str:
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{chrome_version} Safari/537.36"
    )


def generate_profile() -> FingerprintProfile:
    """生成一个逻辑自洽的随机指纹 profile"""
    preset = _pick(ALL_PRESETS)
    chrome_version = _pick(CHROME_VERSIONS)
    screen = _pick(preset.screens)
    dpr = _pick(preset.dprs)
    concurrency = _pick(preset.hardware_concurrencies)
    # deviceMemory >= concurrency 保持正相关
    memory_options = [m for m in preset.device_memories if m >= concurrency]
    memory = _pick(memory_options) if memory_options else _pick(preset.device_memories)

    timezone = "Asia/Shanghai"
    languages = TIMEZONE_LANGUAGES.get(timezone, ["zh-CN", "zh", "en"])
    timezone_offset = TIMEZONE_OFFSETS.get(timezone, -480)

    ua = _build_ua(preset, chrome_version)

    return FingerprintProfile(
        user_agent=ua,
        platform=preset.platform,
        oscpu=preset.oscpu,
        app_version=ua.replace("Mozilla/", ""),
        screen_width=screen[0],
        screen_height=screen[1],
        color_depth=preset.color_depth,
        device_pixel_ratio=dpr,
        hardware_concurrency=concurrency,
        device_memory=memory,
        webgl_vendor=_pick(preset.webgl_vendors),
        webgl_renderer=_pick(preset.webgl_renderers),
        canvas_noise=_random_seed(),
        audio_noise=_random_seed(),
        languages=languages,
        timezone=timezone,
        timezone_offset=timezone_offset,
    )


# ════════════════════════════════════════════════════════════════
# Stealth JS 脚本构建（对应 stealth-script.ts）
# ════════════════════════════════════════════════════════════════

def build_stealth_script(profile: FingerprintProfile) -> str:
    """构建完整的 stealth 注入脚本，返回 JS 字符串"""
    profile_json = json.dumps({
        "userAgent": profile.user_agent,
        "platform": profile.platform,
        "oscpu": profile.oscpu,
        "appVersion": profile.app_version,
        "screenWidth": profile.screen_width,
        "screenHeight": profile.screen_height,
        "colorDepth": profile.color_depth,
        "devicePixelRatio": profile.device_pixel_ratio,
        "hardwareConcurrency": profile.hardware_concurrency,
        "deviceMemory": profile.device_memory,
        "webglVendor": profile.webgl_vendor,
        "webglRenderer": profile.webgl_renderer,
        "canvasNoise": profile.canvas_noise,
        "audioNoise": profile.audio_noise,
        "languages": profile.languages,
        "timezone": profile.timezone,
        "timezoneOffset": profile.timezone_offset,
        "webrtcPolicy": profile.webrtc_policy,
    })

    return f"""(function() {{
  'use strict';
  if (window.__stealth_applied__) return;
  window.__stealth_applied__ = true;

  const profile = {profile_json};

  // === Utility: make overridden functions look native ===
  function makeNative(fn, name) {{
    const nativeToString = function() {{ return 'function ' + name + '() {{ [native code] }}'; }};
    Object.defineProperty(nativeToString, 'name', {{ value: 'toString' }});
    fn.toString = nativeToString;
    return fn;
  }}

  function overrideGetter(obj, prop, value) {{
    try {{
      const desc = Object.getOwnPropertyDescriptor(obj, prop) ||
                   Object.getOwnPropertyDescriptor(Object.getPrototypeOf(obj), prop);
      if (desc && desc.get) {{
        const newGet = makeNative(function() {{ return value; }}, 'get ' + prop);
        Object.defineProperty(obj, prop, {{ get: newGet, configurable: true }});
      }} else {{
        Object.defineProperty(obj, prop, {{ value: value, writable: false, configurable: true }});
      }}
    }} catch(e) {{}}
  }}

  // Seeded PRNG (mulberry32)
  function mulberry32(seed) {{
    return function() {{
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    }};
  }}

  // ===== Navigator / Screen Overrides =====

  try {{
    Object.defineProperty(navigator, 'webdriver', {{
      get: makeNative(function() {{ return false; }}, 'get webdriver'),
      configurable: true,
    }});
  }} catch(e) {{}}

  overrideGetter(navigator, 'platform', profile.platform);
  overrideGetter(navigator, 'languages', Object.freeze([...profile.languages]));
  overrideGetter(navigator, 'language', profile.languages[0]);
  overrideGetter(navigator, 'hardwareConcurrency', profile.hardwareConcurrency);
  overrideGetter(navigator, 'deviceMemory', profile.deviceMemory);

  // Fake PluginArray
  try {{
    const fakePlugins = [
      {{ name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
      {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' }},
      {{ name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }},
    ];
    const pluginArr = Object.create(PluginArray.prototype);
    fakePlugins.forEach((p, i) => {{
      const plugin = Object.create(Plugin.prototype);
      Object.defineProperty(plugin, 'name', {{ value: p.name }});
      Object.defineProperty(plugin, 'filename', {{ value: p.filename }});
      Object.defineProperty(plugin, 'description', {{ value: p.description }});
      Object.defineProperty(plugin, 'length', {{ value: 0 }});
      pluginArr[i] = plugin;
    }});
    Object.defineProperty(pluginArr, 'length', {{ value: fakePlugins.length }});
    pluginArr.item = makeNative(function(i) {{ return pluginArr[i] || null; }}, 'item');
    pluginArr.namedItem = makeNative(function(name) {{
      for (let i = 0; i < pluginArr.length; i++) {{ if (pluginArr[i].name === name) return pluginArr[i]; }}
      return null;
    }}, 'namedItem');
    pluginArr.refresh = makeNative(function() {{}}, 'refresh');
    overrideGetter(navigator, 'plugins', pluginArr);
  }} catch(e) {{}}

  // Screen
  overrideGetter(screen, 'width', profile.screenWidth);
  overrideGetter(screen, 'height', profile.screenHeight);
  overrideGetter(screen, 'availWidth', profile.screenWidth);
  overrideGetter(screen, 'availHeight', profile.screenHeight - 40);
  overrideGetter(screen, 'colorDepth', profile.colorDepth);
  overrideGetter(screen, 'pixelDepth', profile.colorDepth);
  overrideGetter(window, 'devicePixelRatio', profile.devicePixelRatio);

  // window.chrome polyfill
  try {{
    if (!window.chrome) window.chrome = {{}};
    if (!window.chrome.runtime) {{
      window.chrome.runtime = {{
        connect: makeNative(function() {{}}, 'connect'),
        sendMessage: makeNative(function() {{}}, 'sendMessage'),
      }};
    }}
  }} catch(e) {{}}

  // Timezone
  try {{
    const origDTF = Intl.DateTimeFormat;
    const newDTF = makeNative(function(...args) {{
      const instance = new origDTF(...args);
      const origResolved = instance.resolvedOptions.bind(instance);
      instance.resolvedOptions = makeNative(function() {{
        const opts = origResolved();
        opts.timeZone = profile.timezone;
        return opts;
      }}, 'resolvedOptions');
      return instance;
    }}, 'DateTimeFormat');
    newDTF.prototype = origDTF.prototype;
    newDTF.supportedLocalesOf = origDTF.supportedLocalesOf;
    Intl.DateTimeFormat = newDTF;
  }} catch(e) {{}}

  try {{
    Date.prototype.getTimezoneOffset = makeNative(function() {{
      return profile.timezoneOffset;
    }}, 'getTimezoneOffset');
  }} catch(e) {{}}

  // Permissions.query
  try {{
    const origQuery = Permissions.prototype.query;
    Permissions.prototype.query = makeNative(function(desc) {{
      if (desc && desc.name === 'notifications') {{
        return Promise.resolve({{ state: 'prompt', onchange: null }});
      }}
      return origQuery.call(this, desc);
    }}, 'query');
  }} catch(e) {{}}

  // ===== Canvas / WebGL / Audio / WebRTC Noise =====

  // Canvas fingerprint noise
  try {{
    const canvasRng = mulberry32(profile.canvasNoise);
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = makeNative(function(...args) {{
      try {{
        const ctx = this.getContext('2d');
        if (ctx) {{
          const imageData = ctx.getImageData(0, 0, this.width, this.height);
          const data = imageData.data;
          for (let i = 0; i < data.length; i += 4) {{
            data[i] = data[i] + Math.floor((canvasRng() - 0.5) * 2);
            data[i+1] = data[i+1] + Math.floor((canvasRng() - 0.5) * 2);
          }}
          ctx.putImageData(imageData, 0, 0);
        }}
      }} catch(e) {{}}
      return origToDataURL.apply(this, args);
    }}, 'toDataURL');

    const origToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = makeNative(function(...args) {{
      try {{
        const ctx = this.getContext('2d');
        if (ctx) {{
          const imageData = ctx.getImageData(0, 0, this.width, this.height);
          const data = imageData.data;
          for (let i = 0; i < data.length; i += 4) {{
            data[i] = data[i] + Math.floor((canvasRng() - 0.5) * 2);
          }}
          ctx.putImageData(imageData, 0, 0);
        }}
      }} catch(e) {{}}
      return origToBlob.apply(this, args);
    }}, 'toBlob');
  }} catch(e) {{}}

  // WebGL fingerprint
  try {{
    const origGetParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = makeNative(function(pname) {{
      const UNMASKED_VENDOR = 0x9245;
      const UNMASKED_RENDERER = 0x9246;
      if (pname === UNMASKED_VENDOR) return profile.webglVendor;
      if (pname === UNMASKED_RENDERER) return profile.webglRenderer;
      return origGetParam.call(this, pname);
    }}, 'getParameter');

    if (typeof WebGL2RenderingContext !== 'undefined') {{
      const origGetParam2 = WebGL2RenderingContext.prototype.getParameter;
      WebGL2RenderingContext.prototype.getParameter = makeNative(function(pname) {{
        const UNMASKED_VENDOR = 0x9245;
        const UNMASKED_RENDERER = 0x9246;
        if (pname === UNMASKED_VENDOR) return profile.webglVendor;
        if (pname === UNMASKED_RENDERER) return profile.webglRenderer;
        return origGetParam2.call(this, pname);
      }}, 'getParameter');
    }}
  }} catch(e) {{}}

  // AudioContext fingerprint noise
  try {{
    const audioRng = mulberry32(profile.audioNoise);
    const origCreateOscillator = AudioContext.prototype.createOscillator;
    AudioContext.prototype.createOscillator = makeNative(function() {{
      const osc = origCreateOscillator.call(this);
      const origConnect = osc.connect.bind(osc);
      osc.connect = makeNative(function(dest, ...args) {{
        if (dest instanceof AnalyserNode) {{
          const gainNode = osc.context.createGain();
          gainNode.gain.value = 1 + (audioRng() - 0.5) * 0.0001;
          origConnect(gainNode);
          gainNode.connect(dest);
          return dest;
        }}
        return origConnect(dest, ...args);
      }}, 'connect');
      return osc;
    }}, 'createOscillator');
  }} catch(e) {{}}

  // WebRTC block
  try {{
    if (profile.webrtcPolicy === 'block') {{
      window.RTCPeerConnection = makeNative(function() {{
        throw new DOMException('WebRTC is disabled', 'NotAllowedError');
      }}, 'RTCPeerConnection');
      window.webkitRTCPeerConnection = window.RTCPeerConnection;
    }}
  }} catch(e) {{}}

  // ===== iframe sync =====
  try {{
    const observer = new MutationObserver(function(mutations) {{
      mutations.forEach(function(mutation) {{
        mutation.addedNodes.forEach(function(node) {{
          if (node.tagName === 'IFRAME') injectIntoIframe(node);
        }});
      }});
    }});
    observer.observe(document.documentElement, {{ childList: true, subtree: true }});

    function injectIntoIframe(iframe) {{
      const tryInject = function(attempt) {{
        try {{
          const win = iframe.contentWindow;
          if (!win || win.__stealth_applied__) return;
          Object.defineProperty(win.navigator, 'webdriver', {{
            get: function() {{ return false; }},
            configurable: true,
          }});
          win.__stealth_applied__ = true;
        }} catch(e) {{
          if (attempt < 3) requestAnimationFrame(function() {{ tryInject(attempt + 1); }});
        }}
      }};
      iframe.addEventListener('load', function() {{ tryInject(0); }});
      tryInject(0);
    }}

    document.querySelectorAll('iframe').forEach(injectIntoIframe);
  }} catch(e) {{}}

}})();"""


# ════════════════════════════════════════════════════════════════
# HTTP 头伪装（对应 http-spoofing.ts）
# ════════════════════════════════════════════════════════════════

def build_extra_headers(profile: FingerprintProfile) -> dict[str, str]:
    """构建需要设置的额外 HTTP 头"""
    major_version = profile.user_agent.split("Chrome/")[1].split(".")[0] if "Chrome/" in profile.user_agent else "131"
    brand_list = f'"Chromium";v="{major_version}", "Google Chrome";v="{major_version}", "Not-A.Brand";v="8"'

    platform_map = {
        "Win32": '"Windows"',
        "MacIntel": '"macOS"',
        "Linux x86_64": '"Linux"',
    }
    sec_platform = platform_map.get(profile.platform, '"Windows"')

    accept_language = ",".join(
        lang if i == 0 else f"{lang};q={1 - i * 0.1:.1f}"
        for i, lang in enumerate(profile.languages)
    )

    return {
        "Accept-Language": accept_language,
        "Sec-CH-UA": brand_list,
        "Sec-CH-UA-Platform": sec_platform,
        "Sec-CH-UA-Mobile": "?0",
    }
