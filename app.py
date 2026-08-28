
def decodo_ytdlp_options():
    return {
        "proxy": get_decodo_proxy(),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
    }

import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse


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

    from urllib.parse import quote
    user = quote(username, safe="")
    pwd = quote(password, safe="")
    return f"http://{user}:{pwd}@{host}:{port}"

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
    if mime.startswith("image/") or ext in {"jpg","jpeg","png","webp","gif"}:
        return "photo"
    if mime.startswith("video/") or ext in {"mp4","webm","mov","m4v","flv"} or ".m3u8" in u:
        return "video"
    return "media"

def clean(x):
    if not isinstance(x, dict) or not x.get("url"):
        return None
    return {"type":kind(x),"url":x["url"],"ext":x.get("ext"),
            "mime_type":x.get("mime_type"),"width":x.get("width"),
            "height":x.get("height")}

def collect(info):
    result = []
    def walk(x):
        if not isinstance(x, dict): return
        item = clean(x)
        if item: result.append(item)
        for child in x.get("entries") or []: walk(child)
    walk(info)
    seen = set()
    unique = []
    for item in result:
        if item["url"] not in seen:
            seen.add(item["url"]); unique.append(item)
    return unique

@app.get("/")
def home():
    return jsonify({"status":"online","service":"VixRola Universal Media API","engine":"yt-dlp"})

@app.get("/health")
def health():
    return jsonify({"status":"ok"})

@app.route("/download", methods=["GET","POST"])
def download():
    url = request.args.get("url")
    if not url and request.is_json:
        url = (request.get_json(silent=True) or {}).get("url")
    if not url:
        return jsonify({"status":"error","message":"URL is required."}), 400
    if not allowed(url):
        return jsonify({"status":"error","message":"This domain is not enabled."}), 400

    opts = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "noplaylist": False, "extract_flat": False, "format": "best",
        "proxy": get_decodo_proxy()
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        media = collect(info)
        if not media:
            return jsonify({
                "status":"error",
                "message":"No accessible media was returned by yt-dlp. "
                         "The URL may be private, login-required, expired, "
                         "rate-limited, DRM-protected, or unsupported."
            }), 422
        return jsonify({
            "status":"success",
            "platform":host(url),
            "title":info.get("title") or info.get("description") or "Media",
            "media_type":media[0]["type"],
            "download_url":media[0]["url"],
            "media":media,
            "count":len(media)
        })
    except yt_dlp.utils.DownloadError as e:
        return jsonify({
            "status":"error",
            "message":"yt-dlp could not extract this URL. The site or content "
                     "may currently require authentication or may be unsupported.",
            "details":str(e)
        }), 422
    except Exception as e:
        app.logger.exception("Extraction failed")
        return jsonify({"status":"error","message":"Extraction failed.",
                        "details":str(e)}), 500



@app.route("/proxy-test", methods=["GET"])
def proxy_test():
    proxy = get_decodo_proxy()
    if not proxy:
        return {"status":"error","proxy_configured":False,"message":"Decodo environment variables are not configured"}, 500
    try:
        r = requests.get("https://api.ipify.org?format=json", proxies={"http":proxy,"https":proxy}, timeout=20)
        r.raise_for_status()
        data = r.json()
        return {"status":"ok","proxy_configured":True,"proxy_ip":data.get("ip"),"message":"Decodo proxy connection is working"}
    except Exception as e:
        return {"status":"error","proxy_configured":True,"message":"Decodo proxy connection failed","error":str(e)[:500]}, 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
