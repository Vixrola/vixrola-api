from flask import Flask,request,jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse

app=Flask(__name__); CORS(app)
DOMAINS={"facebook.com","fb.watch","instagram.com","youtube.com","youtu.be","tiktok.com","x.com","twitter.com","snapchat.com","telegram.me","t.me","telegram.org","pinterest.com","pin.it","linkedin.com","reddit.com","redd.it","threads.net","discord.com","discord.gg","tumblr.com","vimeo.com","dailymotion.com","dai.ly","twitch.tv","likee.video","kwai.com","kwai-video.com","rumble.com","bilibili.com","b23.tv","triller.co","mojapp.in","joshapp.com","chingari.io","sharechat.com","kooapp.com","roposo.com","public.com","mitron.tv"}

def host(u):
    try:return urlparse(u).netloc.lower().split(":")[0].removeprefix("www.")
    except:return ""
def allowed(u):
    h=host(u); return any(h==d or h.endswith("."+d) for d in DOMAINS)
def kind(x):
    m=(x.get("mime_type") or "").lower(); e=(x.get("ext") or "").lower(); u=(x.get("url") or "").lower()
    if m.startswith("image/") or e in {"jpg","jpeg","png","webp","gif","avif"}: return "photo"
    if m.startswith("video/") or e in {"mp4","webm","mov","m4v","flv","mkv"} or ".m3u8" in u:return "video"
    return "media"
def collect(info):
    out=[]
    def walk(x):
        if not isinstance(x,dict):return
        if x.get("url"):out.append({"type":kind(x),"url":x["url"],"ext":x.get("ext"),"mime_type":x.get("mime_type"),"width":x.get("width"),"height":x.get("height")})
        for y in x.get("entries") or []:walk(y)
    walk(info); seen=set(); r=[]
    for x in out:
        if x["url"] not in seen:seen.add(x["url"]);r.append(x)
    return r

@app.get("/")
def home():return jsonify(status="online",service="VixRola Universal Media API",engine="yt-dlp")
@app.get("/health")
def health():return jsonify(status="ok")
@app.route("/download",methods=["GET","POST"])
def download():
    u=request.args.get("url")
    if not u and request.is_json:u=(request.get_json(silent=True) or {}).get("url")
    if not u:return jsonify(status="error",message="URL is required."),400
    if not allowed(u):return jsonify(status="error",message="This domain is not enabled."),400
    # Do NOT force format='best': Pinterest/Reddit can have no format named 'best'.
    opts={"quiet":True,"no_warnings":True,"skip_download":True,"noplaylist":False,"extract_flat":False,"socket_timeout":30,"retries":2}
    try:
        with yt_dlp.YoutubeDL(opts) as y: info=y.extract_info(u,download=False)
        media=collect(info)
        if not media:return jsonify(status="error",message="No accessible media was returned by yt-dlp."),422
        return jsonify(status="success",platform=host(u),title=info.get("title") or info.get("description") or "Media",media_type=media[0]["type"],download_url=media[0]["url"],media=media,count=len(media))
    except yt_dlp.utils.DownloadError as e:
        return jsonify(status="error",message="yt-dlp could not extract this URL.",details=str(e)),422
    except Exception as e:
        app.logger.exception("Extraction failed");return jsonify(status="error",message="Extraction failed.",details=str(e)),500

if __name__=="__main__":app.run(host="0.0.0.0",port=5000)
