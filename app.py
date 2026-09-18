import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp


# -----------------------------
# VdZip Media API
# -----------------------------

app = Flask(__name__)
CORS(app)

# VdZip supports these 11 platforms.
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


def get_decodo_proxy():
    host = os.getenv("DECODO_HOST", "").strip()
    port = os.getenv("DECODO_PORT", "10001").strip()
    username = os.getenv("DECODO_USERNAME", "").strip()
    password = os.getenv("DECODO_PASSWORD", "").strip()

    if not host or not username or not password:
        return None

    user = quote(username, safe="")
    pwd = quote(password, safe="")
    return f"http://{user}:{pwd}@{host}:{port}"


def host(url):
    try:
        return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    except Exception:
        return ""


def allowed(url):
    h = host(url)
    return any(h == d or h.endswith("." + d) for d in DOMAINS)


def media_kind(x):
    """Classify media without treating audio-only HLS as video."""
    mime = (x.get("mime_type") or "").lower()
    ext = (x.get("ext") or "").lower()
    url = (x.get("url") or "").lower()
    vcodec = (x.get("vcodec") or "").lower()
    acodec = (x.get("acodec") or "").lower()

    if vcodec == "none" and acodec not in ("", "none"):
        return "audio"

    if mime.startswith("audio/"):
        return "audio"

    if mime.startswith("image/") or ext in {
        "jpg", "jpeg", "png", "webp", "gif"
    }:
        return "photo"

    if (
        mime.startswith("video/")
        or vcodec not in ("", "none")
        or ext in {"mp4", "webm", "mov", "m4v", "flv"}
    ):
        return "video"

    # Unknown HLS is kept as media until yt-dlp tells us what it contains.
    if ".m3u8" in url:
        return "media"

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
    result = []

    def walk(item):
        if not isinstance(item, dict):
            return

        for f in item.get("formats") or []:
            media = format_item(f)
            if media:
                result.append(media)

        for child in item.get("entries") or []:
            walk(child)

    walk(info)

    if not result and info.get("url"):
        media = format_item(info)
        if media:
            result.append(media)

    seen = set()
    unique = []
    for item in result:
        key = item["url"]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def media_score(item):
    is_video = 1 if item["type"] == "video" else 0
    has_audio = 1 if (
        item.get("acodec")
        and item["acodec"] != "none"
    ) else 0
    has_video = 1 if (
        item.get("vcodec")
        and item["vcodec"] != "none"
    ) else 0

    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)

    try:
        quality = float(item.get("quality") or -1)
    except (TypeError, ValueError):
        quality = -1

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
            key=lambda x: int(x.get("width") or 0)
            * int(x.get("height") or 0),
        )

    return media[0] if media else None


def ytdlp_base_options():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "extract_flat": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "proxy": get_decodo_proxy(),
    }
    return opts


@app.get("/")
def home():
    return jsonify({
        "status": "online",
        "service": "VdZip Media API",
        "engine": "yt-dlp",
        "platforms": 11,
        "file_download": "/download-file",
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/download", methods=["GET", "POST"])
def download_info():
    """Extract media URLs/metadata only. Does not create a local file."""
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

    opts = ytdlp_base_options()
    opts["skip_download"] = True

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


@app.route("/download-file", methods=["GET", "POST"])
def download_file():
    """
    Download a real media file and, when separate video/audio streams
    are available, let yt-dlp + FFmpeg merge them into MP4.

    Requires FFmpeg/ffprobe on the Render service.
    """
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

    temp_dir = tempfile.mkdtemp(prefix="vdzip_")

    try:
        output_template = str(Path(temp_dir) / "%(title).80s.%(ext)s")

        opts = ytdlp_base_options()
        opts.update({
            # Prefer separate best video + best audio, then fall back to
            # a single combined stream when the site provides one.
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "noplaylist": True,
            "restrictfilenames": True,
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            requested = Path(ydl.prepare_filename(info))

        # Merge output may change the extension to .mp4.
        candidates = list(Path(temp_dir).glob("*"))
        files = [
            p for p in candidates
            if p.is_file()
            and p.suffix.lower() not in {".part", ".ytdl"}
        ]

        if not files:
            return jsonify({
                "status": "error",
                "message": "Download completed but no output file was created."
            }), 500

        # Prefer the final MP4 when present.
        mp4_files = [p for p in files if p.suffix.lower() == ".mp4"]
        final_file = max(mp4_files or files, key=lambda p: p.stat().st_size)

        title = info.get("title") or "vdzip_media"
        safe_name = "".join(
            c if c.isalnum() or c in " .-_()" else "_"
            for c in title
        ).strip() or "vdzip_media"

        download_name = safe_name + ".mp4" if final_file.suffix.lower() == ".mp4" else safe_name + final_file.suffix

        response = send_file(
            final_file,
            as_attachment=True,
            download_name=download_name,
            mimetype="video/mp4" if final_file.suffix.lower() == ".mp4" else None,
        )

        # Flask sends the file after this function returns; cleanup is handled
        # by response.call_on_close.
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response

    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        message = str(e)

        if "ffmpeg" in message.lower():
            message = (
                "FFmpeg is required to merge video and audio. "
                "Install FFmpeg on the Render service."
            )

        return jsonify({
            "status": "error",
            "message": "Media download failed.",
            "details": message[:1500],
        }), 422

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.logger.exception("File download failed")
        return jsonify({
            "status": "error",
            "message": "File download failed.",
            "details": str(e)[:1500],
        }), 500


@app.get("/proxy-test")
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

        return {
            "status": "ok",
            "proxy_configured": True,
            "proxy_ip": r.json().get("ip"),
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
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
