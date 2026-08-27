from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse
import os
import time
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)

DOMAINS = {
"facebook.com","fb.watch","instagram.com","youtube.com","youtu.be",
"tiktok.com","x.com","twitter.com","snapchat.com","telegram.me","t.me",
"telegram.org","pinterest.com","pin.it","linkedin.com","reddit.com",
"redd.it","threads.net","discord.com","discord.gg","tumblr.com","vimeo.com",
"dailymotion.com","dai.ly","twitch.tv","likee.video","kwai.com",
"kwai-video.com","rumble.com","bilibili.com","b23.tv","triller.co",
"mojapp.in","joshapp.com","chingari.io","sharechat.com","kooapp.com",
"roposo.com","public.com","mitron.tv"
}


def host(url):
    try:
        return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    except Exception:
        return ""


def allowed(url):
    h = host(url)
    return any(h == d or h.endswith("." + d) for d in DOMAINS)


def kind(x):
    mime = (x.get("mime_type") or "").lower()
    ext = (x.get("ext") or "").lower()
    u = (x.get("url") or "").lower()
    if mime.startswith("image/") or ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "photo"
    if mime.startswith("video/") or ext in {"mp4", "webm", "mov", "m4v", "flv"} or ".m3u8" in u:
        return "video"
    return "media"


def clean(x):
    if not isinstance(x, dict) or not x.get("url"):
        return None
    return {"type": kind(x), "url": x["url"], "ext": x.get("ext"),
            "mime_type": x.get("mime_type"), "width": x.get("width"),
            "height": x.get("height")}


def collect(info):
    result = []

    def walk(x):
        if not isinstance(x, dict):
            return
        item = clean(x)
        if item:
            result.append(item)
        for child in x.get("entries") or []:
            walk(child)

    walk(info)
    seen = set()
    unique = []
    for item in result:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique


class ProxyPool:
    """Thread-safe round-robin Webshare proxy pool with failure cooldown."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proxies = []
        self.cooldown_until = {}
        self.next_index = 0
        self.cooldown_seconds = max(
            1, int(os.getenv("PROXY_COOLDOWN_SECONDS", "300"))
        )
        self._load()

    def _load(self):
        # Preferred: WEBSHARE_PROXY_1 ... WEBSHARE_PROXY_10
        for i in range(1, 11):
            value = os.getenv(f"WEBSHARE_PROXY_{i}", "").strip()
            if value:
                self.proxies.append(value)

        # Backward-compatible single-proxy fallback.
        if not self.proxies:
            legacy = os.getenv("YTDLP_PROXY", "").strip()
            if legacy:
                self.proxies.append(legacy)

    @property
    def configured(self):
        return bool(self.proxies)

    def get_next(self):
        if not self.proxies:
            return None
        now = time.monotonic()
        with self.lock:
            total = len(self.proxies)
            for _ in range(total):
                idx = self.next_index % total
                self.next_index = (idx + 1) % total
                proxy = self.proxies[idx]
                if self.cooldown_until.get(proxy, 0) <= now:
                    return proxy
        return None

    def mark_failed(self, proxy):
        if not proxy:
            return
        with self.lock:
            self.cooldown_until[proxy] = time.monotonic() + self.cooldown_seconds

    def mark_success(self, proxy):
        if not proxy:
            return
        with self.lock:
            self.cooldown_until.pop(proxy, None)

    def status(self):
        now = time.monotonic()
        with self.lock:
            active = sum(1 for p in self.proxies if self.cooldown_until.get(p, 0) <= now)
            cooldown = sum(1 for p in self.proxies if self.cooldown_until.get(p, 0) > now)
        return {
            "configured": self.configured,
            "total": len(self.proxies),
            "active": active,
            "cooldown": cooldown,
            "cooldown_seconds": self.cooldown_seconds,
        }


proxy_pool = ProxyPool()


def extract_with_proxy(url, proxy):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": False,
        "extract_flat": False,
        "format": "best",
    }
    if proxy:
        opts["proxy"] = proxy

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


@app.get("/")
def home():
    return jsonify({
        "status": "online",
        "service": "VixRola Universal Media API",
        "engine": "yt-dlp",
        "proxy_rotation": proxy_pool.configured,
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok", "proxy_pool": proxy_pool.status()})


@app.get("/proxy-test")
def proxy_test():
    """Test each configured proxy against a fixed Webshare IP endpoint.

    Credentials and proxy URLs are never returned. A successful test clears
    the proxy cooldown; a failed test applies the normal cooldown.
    """
    if not proxy_pool.proxies:
        return jsonify({
            "status": "error",
            "message": "No Webshare proxies are configured."
        }), 503

    target = "https://ipv4.webshare.io/"
    timeout = max(3, min(20, int(os.getenv("PROXY_TEST_TIMEOUT_SECONDS", "10"))))

    def test_one(index_proxy):
        index, proxy = index_proxy
        started = time.monotonic()
        try:
            handler = urllib.request.ProxyHandler({
                "http": proxy,
                "https": proxy,
            })
            opener = urllib.request.build_opener(handler)
            request = urllib.request.Request(
                target,
                headers={"User-Agent": "VixRola-Proxy-Test/1.0"},
            )
            with opener.open(request, timeout=timeout) as response:
                body = response.read(256).decode("utf-8", errors="replace").strip()
            elapsed_ms = round((time.monotonic() - started) * 1000)
            proxy_pool.mark_success(proxy)
            return {
                "proxy": index,
                "status": "ok",
                "http_status": getattr(response, "status", 200),
                "ip": body if body else None,
                "latency_ms": elapsed_ms,
            }
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - started) * 1000)
            proxy_pool.mark_failed(proxy)
            return {
                "proxy": index,
                "status": "failed",
                "error": type(exc).__name__,
                "latency_ms": elapsed_ms,
            }

    indexed = list(enumerate(proxy_pool.proxies, start=1))
    results = []
    workers = min(10, len(indexed))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(test_one, item) for item in indexed]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda x: x["proxy"])
    ok = sum(1 for item in results if item["status"] == "ok")
    failed = len(results) - ok

    return jsonify({
        "status": "ok" if ok else "error",
        "target": "ipv4.webshare.io",
        "tested": len(results),
        "working": ok,
        "failed": failed,
        "results": results,
        "proxy_pool": proxy_pool.status(),
    }), (200 if ok else 502)


@app.route("/download", methods=["GET", "POST"])
def download():
    url = request.args.get("url")
    if not url and request.is_json:
        url = (request.get_json(silent=True) or {}).get("url")
    if not url:
        return jsonify({"status": "error", "message": "URL is required."}), 400
    if not allowed(url):
        return jsonify({"status": "error", "message": "This domain is not enabled."}), 400

    # When Webshare proxies are configured, try each currently available proxy
    # at most once for this request. Failed proxies enter cooldown.
    # If no proxy is configured, yt-dlp runs directly as before.
    attempts = 0
    tried = set()
    max_attempts = len(proxy_pool.proxies) if proxy_pool.proxies else 1

    while attempts < max_attempts:
        proxy = proxy_pool.get_next() if proxy_pool.configured else None

        if proxy_pool.configured and not proxy:
            return jsonify({
                "status": "error",
                "message": "All configured proxies are temporarily in cooldown. Please try again shortly."
            }), 503

        if proxy in tried:
            continue
        tried.add(proxy)
        attempts += 1

        try:
            info = extract_with_proxy(url, proxy)
            media = collect(info)
            if not media:
                # Treat an extraction that returns no usable media as a failed
                # proxy attempt so another proxy can be tried.
                if proxy:
                    proxy_pool.mark_failed(proxy)
                continue

            if proxy:
                proxy_pool.mark_success(proxy)

            return jsonify({
                "status": "success",
                "platform": host(url),
                "title": info.get("title") or info.get("description") or "Media",
                "media_type": media[0]["type"],
                "download_url": media[0]["url"],
                "media": media,
                "count": len(media)
            })

        except yt_dlp.utils.DownloadError as e:
            if proxy:
                proxy_pool.mark_failed(proxy)
            app.logger.warning("yt-dlp extraction failed using proxy %s: %s", attempts, e)
            continue
        except Exception as e:
            if proxy:
                proxy_pool.mark_failed(proxy)
            app.logger.exception("Extraction failed using proxy %s", attempts)
            continue

    return jsonify({
        "status": "error",
        "message": "yt-dlp could not extract this URL with the available proxies. "
                   "The content may be private, login-required, expired, restricted, "
                   "DRM-protected, unsupported, rate-limited, or all proxies may have failed.",
        "attempts": attempts,
    }), 422


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
