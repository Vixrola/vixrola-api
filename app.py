from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

DOMAINS = {
    "facebook.com","fb.watch","instagram.com","youtube.com","youtu.be",
    "tiktok.com","x.com","twitter.com","snapchat.com",
    "telegram.me","t.me","telegram.org","pinterest.com","pin.it",
    "linkedin.com","reddit.com","redd.it",
    "threads.net","threads.com",
    "tumblr.com","vimeo.com","dailymotion.com","dai.ly",
    "likee.video","kwai.com","kwai-video.com","rumble.com",
    "bilibili.com","b23.tv","triller.co","mojapp.in",
    "joshapp.com","joshapp.in","myjosh.in","joshapp.net",
    "chingari.io","sharechat.com","kooapp.com","roposo.com",
    "public.com","mitron.tv"
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
    if mime.startswith("video/") or ext in {"mp4","webm","mov","m4v","flv","mkv"} or ".m3u8" in u:
        return "video"
    if mime.startswith("image/") or ext in {"jpg","jpeg","png","webp","gif","avif"}:
        return "photo"
    return "media"

def collect(info):
    found = []
    def walk(x):
        if not isinstance(x, dict):
            return
        if x.get("url"):
            found.append({
                "type": kind(x),
                "url": x["url"],
                "ext": x.get("ext"),
                "format_id": x.get("format_id"),
                "mime_type": x.get("mime_type"),
                "width": x.get("width"),
                "height": x.get("height")
            })
        for y in x.get("entries") or []:
            walk(y)
    walk(info)
    seen, out = set(), []
    for m in found:
        if m["url"] not in seen:
            seen.add(m["url"])
            out.append(m)
    return out

def yt_extract(url):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "noplaylist": False,
        "socket_timeout": 30,
        "retries": 2,
    }
    with yt_dlp.YoutubeDL(opts) as y:
        return y.extract_info(url, download=False)

@app.get("/")
def home():
    return jsonify(status="online", service="VixRola Universal Video API", version="5", engine="yt-dlp")

@app.get("/health")
def health():
    return jsonify(status="ok", version="5")

@app.route("/download", methods=["GET","POST"])
def download():
    url = request.args.get("url")
    if not url and request.is_json:
        url = (request.get_json(silent=True) or {}).get("url")

    if not url:
        return jsonify(status="error", message="URL is required."), 400
    if not allowed(url):
        return jsonify(status="error", message="This domain is not enabled."), 400

    h = host(url)

    try:
        info = yt_extract(url)
        media = collect(info)
        videos = [m for m in media if m["type"] == "video"]

        if not videos:
            return jsonify(status="error", platform=h,
                           message="No accessible video media was returned by yt-dlp."), 422

        def score(m):
            u = m["url"].lower()
            s = 0
            if m.get("ext") == "mp4": s += 50
            if ".m3u8" not in u: s += 20
            if m.get("height"):
                try: s += min(int(m["height"]), 2160) / 1000
                except: pass
            return s

        videos.sort(key=score, reverse=True)

        return jsonify(
            status="success",
            platform=h,
            title=info.get("title") or info.get("description") or "Video",
            media_type="video",
            download_url=videos[0]["url"],
            media=videos,
            count=len(videos)
        )

    except yt_dlp.utils.DownloadError as e:
        return jsonify(status="error", platform=h,
                       message="yt-dlp could not extract this video.",
                       details=str(e)), 422
    except Exception as e:
        app.logger.exception("Extraction failed")
        return jsonify(status="error", platform=h,
                       message="Extraction failed.", details=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
