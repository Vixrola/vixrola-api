import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse, quote

# --- Decodo Residential Proxy (Render Environment Variables) ---
def get_decodo_proxy():
    """Build a yt-dlp-compatible Decodo proxy URL from Render env vars.
    Returns None when Decodo variables are not configured.
    """
    host = os.getenv("DECODO_HOST", "").strip()
    port = os.getenv("DECODO_PORT", "10001").strip()
    username = os.getenv("DECODO_USERNAME", "").strip()
    password = os.getenv("DECODO_PASSWORD", "").strip()

    if not host or not username or not password:
        return None

    user = quote(username, safe="")
    pwd = quote(password, safe="")
    return f"http://{user}:{pwd}@{host}:{port}"


app = Flask(__name__)
CORS(app)

# VdZip supports only these 11 platforms.
# Aliases below belong to the same platform (for example pin.it -> Pinterest).
DOMAINS = {
    "facebook.com", "fb.watch",
    "instagram.com",
    "x.com", "twitter.com",
    "pinterest.com", "pin.it",
    "reddit.com", "redd.it",
    "linkedin.com",
    "snapchat.com",
    "mojapp.in",
    "joshapp.com",
    "tiktok.com",
    "dailymotion.com", "dai.ly",
}


def host(url):
    try:
        return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    except Exception:
        return ""


def allowed(url):
    h = host(url)
    return any(h == d or h.endswith("." + d) for d in DOMAINS)


def media_kind(x):
    mime = (x.get("mime_type") or "").lower()
    ext = (x.get("ext") or "").lower()
    u = (x.get("url") or "").lower()

    if mime.startswith("image/") or ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "photo"

    if (
        mime.startswith("video/")
        or ext in {"mp4", "webm", "mov", "m4v", "flv"}
        or ".m3u8" in u
    ):
        return "video"

    return "media"


def format_item(f):
    if not isinstance(f, dict) or not f.get("url"):
        return None

    return {
        "type": media_kind(f),
        "url": f["url"],
        "ext": f.get("ext"),
        "mime_type": f.get("mime_type"),
        "width": f.get("width"),
        "height": f.get("height"),
        "format_id": f.get("format_id"),
        "filesize": f.get("filesize") or f.get("filesize_approx"),
        "vcodec": f.get("vcodec"),
        "acodec": f.get("acodec"),
        "fps": f.get("fps"),
        "quality": f.get("quality"),
    }


def collect_formats(info):
    """Collect actual media URLs from yt-dlp's returned formats.

    Important: we intentionally do NOT pass a fixed `format` selector to
    yt-dlp. Pinterest and Reddit can expose different format IDs depending
    on the post, and a fixed selector can cause:
    'Requested format is not available'.
    """
    result = []

    def walk(x):
        if not isinstance(x, dict):
            return

        for f in x.get("formats") or []:
            item = format_item(f)
            if item:
                result.append(item)

        # Handle playlist/carousel entries as well.
        for child in x.get("entries") or []:
            walk(child)

    walk(info)

    # Some extractors can return a direct URL even when formats is absent.
    if not result and info.get("url"):
        item = format_item(info)
        if item:
            result.append(item)

    seen = set()
    unique = []
    for item in result:
        key = item["url"]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def media_score(item):
    """Prefer a playable video with both video+audio, then video-only."""
    is_video = 1 if item["type"] == "video" else 0
    has_audio = 1 if (item.get("acodec") and item["acodec"] != "none") else 0
    has_video = 1 if (item.get("vcodec") and item["vcodec"] != "none") else 0
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    quality = float(item.get("quality") or -1)

    # Combined video+audio is preferred for a one-click direct download.
    return (
        is_video,
        has_audio,
        has_video,
        width * height,
        quality,
    )


def choose_download_format(media):
    videos = [m for m in media if m["type"] == "video"]
    if videos:
        return max(videos, key=media_score)

    photos = [m for m in media if m["type"] == "photo"]
    if photos:
        return max(
            photos,
            key=lambda x: int(x.get("width") or 0) * int(x.get("height") or 0),
        )

    return media[0] if media else None


@app.get("/")
def home():
    return jsonify({
        "status": "online",
        "service": "VdZip Media API",
        "engine": "yt-dlp",
        "platforms": 11,
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/download", methods=["GET", "POST"])
def download():
    url = request.args.get("url")

    if not url and request.is_json:
        url = (request.get_json(silent=True) or {}).get("url")

    if not url:
        return jsonify({
            "status": "error",
            "message": "URL is required."
        }), 400

    if not allowed(url):
        return jsonify({
            "status": "error",
            "message": "This platform is not enabled. VdZip supports 11 platforms only."
        }), 400

    # Do not use format="best" or another fixed selector here.
    # Pinterest/Reddit may not expose that exact selector.
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": False,
        "extract_flat": False,
        "proxy": get_decodo_proxy(),
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        media = collect_formats(info)

        if not media:
            return jsonify({
                "status": "error",
                "message": (
                    "No accessible media was returned by yt-dlp. "
                    "The URL may be private, login-required, expired, "
                    "rate-limited, DRM-protected, or unsupported."
                )
            }), 422

        selected = choose_download_format(media)

        # Put the selected format first so existing VdZip frontend code can
        # continue using media[0] / download_url.
        if selected:
            media = [selected] + [
                m for m in media if m["url"] != selected["url"]
            ]

        return jsonify({
            "status": "success",
            "platform": host(url),
            "title": info.get("title") or info.get("description") or "Media",
            "thumbnail": info.get("thumbnail"),
            "media_type": media[0]["type"],
            "download_url": media[0]["url"],
            "media": media,
            "count": len(media),
        })

    except yt_dlp.utils.DownloadError as e:
        return jsonify({
            "status": "error",
            "message": (
                "yt-dlp could not extract this URL. "
                "The site or content may currently require authentication "
                "or may be unsupported."
            ),
            "details": str(e),
        }), 422

    except Exception as e:
        app.logger.exception("Extraction failed")
        return jsonify({
            "status": "error",
            "message": "Extraction failed.",
            "details": str(e),
        }), 500


@app.route("/proxy-test", methods=["GET"])
def proxy_test():
    proxy = get_decodo_proxy()

    if not proxy:
        return {
            "status": "error",
            "proxy_configured": False,
            "message": "Decodo environment variables are not configured"
        }, 500

    try:
        r = requests.get(
            "https://api.ipify.org?format=json",
            proxies={"http": proxy, "https": proxy},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()

        return {
            "status": "ok",
            "proxy_configured": True,
            "proxy_ip": data.get("ip"),
            "message": "Decodo proxy connection is working",
        }

    except Exception as e:
        return {
            "status": "error",
            "proxy_configured": True,
            "message": "Decodo proxy connection failed",
            "error": str(e)[:500],
        }, 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
