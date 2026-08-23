from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

SUPPORTED_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.watch",
}

def is_supported_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        return host in SUPPORTED_HOSTS or host.endswith(".facebook.com")
    except Exception:
        return False

def media_type(item):
    """Return a frontend-friendly media type."""
    ext = (item.get("ext") or "").lower()
    url = (item.get("url") or "").lower()
    mime = (item.get("mime_type") or "").lower()

    if mime.startswith("image/") or ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "photo"
    if mime.startswith("video/") or ext in {"mp4", "mov", "webm", "m4v"}:
        return "video"
    if ".m3u8" in url or "m3u8" in mime:
        return "video"
    return "media"

def clean_media(item):
    url = item.get("url")
    if not url:
        return None

    return {
        "type": media_type(item),
        "url": url,
        "ext": item.get("ext"),
        "mime_type": item.get("mime_type"),
        "width": item.get("width"),
        "height": item.get("height"),
        "title": item.get("title") or item.get("description") or "Media",
    }

def collect_media(info):
    """
    Collect direct media URLs from a yt-dlp result.
    Handles normal posts and multi-item/carousel results.
    """
    media = []

    def walk(item):
        if not isinstance(item, dict):
            return

        # Prefer the extracted direct URL.
        candidate = clean_media(item)
        if candidate:
            media.append(candidate)

        # Carousel / playlist / multi-media result.
        for child in item.get("entries") or []:
            walk(child)

    walk(info)

    # Remove duplicate URLs while keeping order.
    unique = []
    seen = set()
    for item in media:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "message": "VixRola API is running!",
        "version": "2.0"
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/download", methods=["GET", "POST"])
def download():
    url = request.args.get("url")

    if not url and request.is_json:
        data = request.get_json(silent=True) or {}
        url = data.get("url")

    if not url:
        return jsonify({
            "status": "error",
            "message": "Please provide a valid Instagram or Facebook URL."
        }), 400

    if not is_supported_url(url):
        return jsonify({
            "status": "error",
            "message": "Only Instagram and Facebook URLs are supported."
        }), 400

    # Best available single media. For images this allows the extractor
    # to return the image URL instead of forcing a video-only format.
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": False,
        "extract_flat": False,
        "format": "best",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        media = collect_media(info)

        if not media:
            return jsonify({
                "status": "error",
                "message": (
                    "No downloadable public media was found. "
                    "The post may be private, login-required, expired, "
                    "or unsupported by the current extractor."
                )
            }), 404

        videos = [m for m in media if m["type"] == "video"]
        photos = [m for m in media if m["type"] == "photo"]

        # Backward-compatible response: download_url remains available.
        first = media[0]

        return jsonify({
            "status": "success",
            "title": info.get("title") or info.get("description") or "Media",
            "media_type": first["type"],
            "download_url": first["url"],
            "media": media,
            "count": len(media),
            "video_count": len(videos),
            "photo_count": len(photos),
        })

    except yt_dlp.utils.DownloadError as e:
        return jsonify({
            "status": "error",
            "message": (
                "This URL could not be extracted. It may be private, "
                "login-required, expired, rate-limited, or unsupported. "
                f"Details: {str(e)}"
            )
        }), 422
    except Exception as e:
        app.logger.exception("Download endpoint failed")
        return jsonify({
            "status": "error",
            "message": "The server could not process this URL.",
            "details": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
