from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Only the 10 platforms that were actually tested successfully.
DOMAINS = {
    "instagram.com",
    "facebook.com", "fb.watch",
    "x.com", "twitter.com",
    "pinterest.com", "pin.it",
    "reddit.com", "redd.it",
    "snapchat.com",
    "telegram.me", "t.me", "telegram.org",
    "linkedin.com",
    "mojapp.in",
    "joshapp.com", "joshapp.in", "myjosh.in",
    "share.myjosh.in",
}

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
        if not isinstance(f, dict):
            continue
        if not f.get("url") or not is_video(f):
            continue
        found.append({
            "type": "video",
            "url": f["url"],
            "ext": f.get("ext"),
            "format_id": f.get("format_id"),
            "mime_type": f.get("mime_type"),
            "width": f.get("width"),
            "height": f.get("height"),
        })

    direct = info.get("url")
    if direct and not found:
        f = {
            "url": direct,
            "ext": info.get("ext"),
            "format_id": info.get("format_id"),
            "mime_type": info.get("mime_type"),
            "vcodec": info.get("vcodec"),
        }
        if is_video(f):
            found.append({
                "type": "video",
                "url": direct,
                "ext": f.get("ext"),
                "format_id": f.get("format_id"),
                "mime_type": f.get("mime_type"),
                "width": info.get("width"),
                "height": info.get("height"),
            })

    # De-duplicate
    unique, seen = [], set()
    for item in found:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique

@app.get("/")
def home():
    return jsonify(status="online", message="VixRola API is running!", version="4")

@app.get("/health")
def health():
    return jsonify(
        status="ok",
        version="4",
        yt_dlp_version=yt_dlp.version.__version__
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

    ydl_opts = {
        "format": "bestvideo*+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        media = extract_media(info)

        # If yt-dlp selected a direct video URL, preserve it exactly.
        if not media and info.get("url"):
            media = [{
                "type": "video",
                "url": info["url"],
                "ext": info.get("ext"),
                "format_id": info.get("format_id"),
                "mime_type": info.get("mime_type"),
                "width": info.get("width"),
                "height": info.get("height"),
            }]

        if not media:
            return jsonify(
                status="error",
                platform=host(url),
                message="No accessible video media was returned by yt-dlp."
            ), 422

        def score(x):
            s = 0
            if (x.get("ext") or "").lower() == "mp4":
                s += 100
            if ".m3u8" not in (x.get("url") or "").lower():
                s += 20
            try:
                s += min(int(x.get("height") or 0), 2160) / 10
            except Exception:
                pass
            return s

        media.sort(key=score, reverse=True)

        return jsonify(
            status="success",
            title=info.get("title", "Video"),
            platform=host(url),
            media_type="video",
            download_url=media[0]["url"],
            media=media,
            count=len(media)
        )

    except Exception as e:
        return jsonify(
            status="error",
            platform=host(url),
            message="yt-dlp could not extract this video.",
            details=str(e)
        ), 422

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
