from flask import Flask, request, jsonify
import os
import time
import threading
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Only the platforms in the existing test build.
DOMAINS = {
    "instagram.com", "facebook.com", "fb.watch", "x.com", "twitter.com",
    "pinterest.com", "pin.it", "reddit.com", "redd.it", "snapchat.com",
    "telegram.me", "t.me", "telegram.org", "linkedin.com", "mojapp.in",
    "joshapp.com", "joshapp.in", "myjosh.in", "share.myjosh.in", "tiktok.com",
    "vt.tiktok.com", "threads.com", "threads.net", "youtube.com", "youtu.be",
    "youtube-nocookie.com", "vimeo.com", "dailymotion.com", "dai.ly", "triller.co",
    "bilibili.com", "b23.tv",
}

# -----------------------------------------------------------------------------
# Webshare rotating proxy pool
# -----------------------------------------------------------------------------
# Preferred configuration on Render:
#   WEBSHARE_PROXY_1 ... WEBSHARE_PROXY_10
# Each value should be a complete proxy URL, e.g.
#   http://USERNAME:PASSWORD@HOST:PORT
#
# Also supported for convenience:
#   WEBSHARE_PROXIES = one proxy URL per line, comma, or whitespace separated.
#
# Failed proxies are put into a temporary cooldown so a bad IP is not retried
# immediately. The pool is process-local (appropriate for a single Render
# instance); each Render instance maintains its own pool.
PROXY_COOLDOWN_SECONDS = max(30, int(os.getenv("PROXY_COOLDOWN_SECONDS", "300")))
PROXY_LOCK = threading.Lock()
PROXY_STATE = {}  # proxy -> {"cooldown_until": float, "failures": int}
PROXY_CURSOR = 0


def load_proxies():
    proxies = []
    for i in range(1, 11):
        value = os.getenv(f"WEBSHARE_PROXY_{i}", "").strip()
        if value:
            proxies.append(value)

    # Optional bulk variable; useful if the provider gives a list.
    bulk = os.getenv("WEBSHARE_PROXIES", "").strip()
    if bulk:
        for item in bulk.replace(",", "\n").splitlines():
            item = item.strip()
            if item:
                proxies.append(item)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(proxies))


def acquire_proxy():
    """Return the next available proxy using round-robin selection."""
    global PROXY_CURSOR
    proxies = load_proxies()
    if not proxies:
        return None

    now = time.time()
    with PROXY_LOCK:
        for proxy in proxies:
            PROXY_STATE.setdefault(proxy, {"cooldown_until": 0.0, "failures": 0})

        for offset in range(len(proxies)):
            index = (PROXY_CURSOR + offset) % len(proxies)
            proxy = proxies[index]
            state = PROXY_STATE[proxy]
            if state["cooldown_until"] <= now:
                PROXY_CURSOR = (index + 1) % len(proxies)
                return proxy

    return None


def mark_proxy_success(proxy):
    if not proxy:
        return
    with PROXY_LOCK:
        state = PROXY_STATE.setdefault(proxy, {"cooldown_until": 0.0, "failures": 0})
        state["failures"] = 0
        state["cooldown_until"] = 0.0


def mark_proxy_failed(proxy):
    if not proxy:
        return
    with PROXY_LOCK:
        state = PROXY_STATE.setdefault(proxy, {"cooldown_until": 0.0, "failures": 0})
        state["failures"] += 1
        # Keep a fixed cooldown for predictable behavior. A second failure is
        # still cooled down instead of hammering the same IP.
        state["cooldown_until"] = time.time() + PROXY_COOLDOWN_SECONDS


def proxy_pool_status():
    proxies = load_proxies()
    now = time.time()
    with PROXY_LOCK:
        available = sum(
            1 for p in proxies
            if PROXY_STATE.get(p, {}).get("cooldown_until", 0) <= now
        )
        cooldown = sum(1 for p in proxies if p in PROXY_STATE and PROXY_STATE[p].get("cooldown_until", 0) > now)
    return len(proxies), available, cooldown


def host(url):
    try:
        return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    except Exception:
        return ""


def allowed(url):
    h = host(url)
    return any(h == d or h.endswith("." + d) for d in DOMAINS)


def is_video(f):
    if not isinstance(f, dict):
        return False
    vcodec = f.get("vcodec")
    if vcodec and vcodec != "none":
        return True
    mime = (f.get("mime_type") or "").lower()
    if mime.startswith("video/"):
        return True
    ext = (f.get("ext") or "").lower()
    if ext in {"mp4", "webm", "mov", "m4v", "mkv", "flv", "ts"}:
        return True
    u = (f.get("url") or "").lower()
    return ".m3u8" in u or any(x in u for x in (
        "video.twimg.com/", "v.redd.it/", "pinimg.com/videos/",
        "cdninstagram.com/", "fbcdn.net/", "sc-cdn.net/",
        "telesco.pe/", "licdn.com/", "myjosh.in/",
        "share.myjosh.in/", "mojapp.in/"
    ))


def extract_media(info):
    formats = info.get("formats") or []
    found = []

    for f in formats:
        if not isinstance(f, dict) or not f.get("url") or not is_video(f):
            continue
        found.append({
            "type": "video", "url": f["url"], "ext": f.get("ext"),
            "format_id": f.get("format_id"), "mime_type": f.get("mime_type"),
            "width": f.get("width"), "height": f.get("height"),
        })

    direct = info.get("url")
    if direct and not found:
        f = {"url": direct, "ext": info.get("ext"), "format_id": info.get("format_id"),
             "mime_type": info.get("mime_type"), "vcodec": info.get("vcodec")}
        if is_video(f):
            found.append({
                "type": "video", "url": direct, "ext": f.get("ext"),
                "format_id": f.get("format_id"), "mime_type": f.get("mime_type"),
                "width": info.get("width"), "height": info.get("height"),
            })

    unique, seen = [], set()
    for item in found:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique


def extract_with_proxy(url, proxy, cookies_file):
    ydl_opts = {
        "format": "bestvideo*+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    if proxy:
        ydl_opts["proxy"] = proxy
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


@app.get("/")
def home():
    total, available, cooldown = proxy_pool_status()
    return jsonify(status="online", message="VixRola API is running!", version="5",
                   proxy_pool=total, proxies_available=available, proxies_cooldown=cooldown)


@app.get("/health")
def health():
    total, available, cooldown = proxy_pool_status()
    return jsonify(
        status="ok", version="5", yt_dlp_version=yt_dlp.version.__version__,
        proxy_pool_configured=total > 0, proxy_pool_size=total,
        proxies_available=available, proxies_cooldown=cooldown,
        legacy_proxy_configured=bool(os.getenv("YTDLP_PROXY")),
        cookies_configured=bool(os.getenv("YTDLP_COOKIES_FILE")),
        proxy_cooldown_seconds=PROXY_COOLDOWN_SECONDS,
    )


@app.route("/download", methods=["GET", "POST"])
def download():
    url = request.args.get("url")
    if not url and request.is_json:
        data = request.get_json(silent=True) or {}
        url = data.get("url")

    if not url:
        return jsonify(status="error", message="Please provide a valid URL"), 400
    if not allowed(url):
        return jsonify(status="error", message="This domain is not enabled."), 400

    cookies_file = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    proxies = load_proxies()

    # If Webshare pool is configured, try each currently available proxy once.
    # Otherwise retain compatibility with the old single YTDLP_PROXY setting.
    if proxies:
        attempted = []
        last_error = None
        max_attempts = len(proxies)
        for _ in range(max_attempts):
            proxy = acquire_proxy()
            if not proxy:
                break
            attempted.append(proxy)
            try:
                info = extract_with_proxy(url, proxy, cookies_file)
                mark_proxy_success(proxy)
                break
            except Exception as e:
                last_error = e
                mark_proxy_failed(proxy)
        else:
            info = None

        if 'info' not in locals() or info is None:
            # All available proxies failed. Do not immediately hammer cooled
            # down proxies; report a retryable error.
            return jsonify(
                status="error", platform=host(url),
                message="All available Webshare proxies failed or are on cooldown.",
                details=str(last_error) if last_error else "No proxy is currently available.",
                attempted_proxies=len(attempted),
                cooldown_seconds=PROXY_COOLDOWN_SECONDS,
            ), 503
    else:
        # Backward-compatible single proxy mode.
        proxy = os.getenv("YTDLP_PROXY", "").strip()
        try:
            info = extract_with_proxy(url, proxy, cookies_file)
        except Exception as e:
            return jsonify(status="error", platform=host(url),
                           message="yt-dlp could not extract this video.", details=str(e)), 422

    # Telegram can return None entries in formats.
    if host(url) in {"t.me", "telegram.me", "telegram.org"} and isinstance(info, dict):
        formats = info.get("formats")
        if isinstance(formats, list):
            info["formats"] = [f for f in formats if isinstance(f, dict)]

    media = extract_media(info)
    if not media and info.get("url"):
        media = [{"type": "video", "url": info["url"], "ext": info.get("ext"),
                  "format_id": info.get("format_id"), "mime_type": info.get("mime_type"),
                  "width": info.get("width"), "height": info.get("height")}]

    if not media:
        return jsonify(status="error", platform=host(url),
                       message="No accessible video media was returned by yt-dlp."), 422

    def score(x):
        s = 0
        if (x.get("ext") or "").lower() == "mp4": s += 100
        if ".m3u8" not in (x.get("url") or "").lower(): s += 20
        try: s += min(int(x.get("height") or 0), 2160) / 10
        except Exception: pass
        return s

    media.sort(key=score, reverse=True)
    return jsonify(status="success", title=info.get("title", "Video"),
                   platform=host(url), media_type="video", download_url=media[0]["url"],
                   media=media, count=len(media))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
