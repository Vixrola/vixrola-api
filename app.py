import os
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse, quote
import tempfile
import glob

def get_decodo_proxy():
    host = os.getenv("DECODO_HOST", "").strip()
    port = os.getenv("DECODO_PORT", "10001").strip()
    username = os.getenv("DECODO_USERNAME", "").strip()
    password = os.getenv("DECODO_PASSWORD", "").strip()
    if not host or not username or not password:
        return None
    return f"http://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{port}"

app = Flask(__name__)
CORS(app)

DOMAINS = {
    "facebook.com", "fb.watch", "instagram.com",
    "x.com", "twitter.com", "pinterest.com", "pin.it",
    "reddit.com", "redd.it", "linkedin.com", "snapchat.com",
    "mojapp.in", "joshapp.com", "tiktok.com",
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

def proxy_for_url(url):
    # ALL supported platforms use the configured Decodo proxy.
    # yt-dlp supports HTTP/HTTPS/SOCKS proxy URLs through its proxy option.
    return get_decodo_proxy()

def ytdlp_options(url, download=False, output_template=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 15,
        "noplaylist": True,
        "extract_flat": False,
        "concurrent_fragment_downloads": 8,
        "proxy": proxy_for_url(url),
    }
    if download:
        opts.update({
            "format": "best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "restrictfilenames": True,
        })
    else:
        opts["skip_download"] = True
    return opts

def media_kind(x):
    mime = (x.get("mime_type") or "").lower()
    ext = (x.get("ext") or "").lower()
    u = (x.get("url") or "").lower()
    vcodec = (x.get("vcodec") or "").lower()
    acodec = (x.get("acodec") or "").lower()

    if mime.startswith("image/") or ext in {"jpg","jpeg","png","webp","gif"}:
        return "photo"
    if vcodec == "none" and acodec not in ("", "none"):
        return "audio"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/") or ext in {"mp4","webm","mov","m4v","flv"}:
        return "video"
    if vcodec not in ("", "none"):
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
    result = []
    def walk(x):
        if not isinstance(x, dict):
            return
        for f in x.get("formats") or []:
            item = format_item(f)
            if item:
                result.append(item)
        for child in x.get("entries") or []:
            walk(child)
    walk(info)
    if not result and info.get("url"):
        item = format_item(info)
        if item:
            result.append(item)
    seen, unique = set(), []
    for item in result:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique

def media_score(item):
    return (
        1 if item["type"] == "video" else 0,
        1 if item.get("acodec") not in (None, "", "none") else 0,
        1 if item.get("vcodec") not in (None, "", "none") else 0,
        int(item.get("width") or 0) * int(item.get("height") or 0),
        float(item.get("quality") or -1),
    )

def choose_download_format(media):
    videos = [m for m in media if m["type"] == "video"]
    if videos:
        return max(videos, key=media_score)
    photos = [m for m in media if m["type"] == "photo"]
    if photos:
        return max(photos, key=lambda x: int(x.get("width") or 0)*int(x.get("height") or 0))
    return media[0] if media else None

@app.get("/")
def home():
    return jsonify({"status":"online","service":"VdZip Media API","engine":"yt-dlp","platforms":11})

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
        return jsonify({"status":"error","message":"This platform is not enabled. VdZip supports 11 platforms only."}), 400

    try:
        with yt_dlp.YoutubeDL(ytdlp_options(url, download=False)) as ydl:
            info = ydl.extract_info(url, download=False)
        media = collect_formats(info)
        if not media:
            return jsonify({"status":"error","message":"No accessible media was returned by yt-dlp."}), 422
        selected = choose_download_format(media)
        if selected:
            media = [selected] + [m for m in media if m["url"] != selected["url"]]
        return jsonify({
            "status":"success","platform":host(url),
            "title":info.get("title") or info.get("description") or "Media",
            "thumbnail":info.get("thumbnail"),
            "media_type":media[0]["type"],
            "download_url":media[0]["url"],
            "media":media,"count":len(media),
            "proxy_mode":"decodo" if proxy_for_url(url) else "direct"
        })
    except yt_dlp.utils.DownloadError as e:
        return jsonify({"status":"error","message":"yt-dlp could not extract this URL.","details":str(e)}), 422
    except Exception as e:
        app.logger.exception("Extraction failed")
        return jsonify({"status":"error","message":"Extraction failed.","details":str(e)}), 500

@app.route("/download-file", methods=["GET","POST"])
def download_file():
    url = request.args.get("url")
    if not url and request.is_json:
        url = (request.get_json(silent=True) or {}).get("url")
    if not url:
        return jsonify({"status":"error","message":"URL is required."}), 400
    if not allowed(url):
        return jsonify({"status":"error","message":"This platform is not enabled."}), 400

    temp_dir = tempfile.mkdtemp(prefix="vdzip_")
    output_template = os.path.join(temp_dir, "%(title).120s.%(ext)s")
    try:
        with yt_dlp.YoutubeDL(ytdlp_options(url, download=True, output_template=output_template)) as ydl:
            info = ydl.extract_info(url, download=True)
            requested = ydl.prepare_filename(info)

        candidates = [p for p in glob.glob(os.path.join(temp_dir, "*")) if os.path.isfile(p)]
        if not candidates:
            return jsonify({"status":"error","message":"Downloaded file was not created."}), 500

        mp4s = [p for p in candidates if p.lower().endswith(".mp4")]
        path = mp4s[0] if mp4s else max(candidates, key=os.path.getsize)

        response = send_file(path, as_attachment=True, download_name=os.path.basename(path), mimetype="video/mp4" if path.lower().endswith(".mp4") else None)
        response.call_on_close(lambda: __import__("shutil").rmtree(temp_dir, ignore_errors=True))
        return response
    except yt_dlp.utils.DownloadError as e:
        __import__("shutil").rmtree(temp_dir, ignore_errors=True)
        return jsonify({"status":"error","message":"yt-dlp could not download this URL.","details":str(e)}), 422
    except Exception as e:
        __import__("shutil").rmtree(temp_dir, ignore_errors=True)
        return jsonify({"status":"error","message":"Download failed.","details":str(e)}), 500

@app.get("/proxy-test")
def proxy_test():
    proxy = get_decodo_proxy()
    if not proxy:
        return {"status":"error","proxy_configured":False,"message":"Decodo environment variables are not configured"}, 500
    try:
        r = requests.get("https://api.ipify.org?format=json", proxies={"http":proxy,"https":proxy}, timeout=20)
        r.raise_for_status()
        return {"status":"ok","proxy_configured":True,"proxy_ip":r.json().get("ip"),"message":"Decodo proxy connection is working"}
    except Exception as e:
        return {"status":"error","proxy_configured":True,"message":"Decodo proxy connection failed","error":str(e)[:500]}, 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")))
