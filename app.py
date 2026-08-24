from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse
app=Flask(__name__); CORS(app)
DOMAINS={"facebook.com","fb.watch","instagram.com","youtube.com","youtu.be","tiktok.com","x.com","twitter.com","snapchat.com","telegram.me","t.me","telegram.org","pinterest.com","pin.it","linkedin.com","reddit.com","redd.it","threads.net","threads.com","discord.com","discord.gg","tumblr.com","vimeo.com","dailymotion.com","dai.ly","likee.video","kwai.com","kwai-video.com","rumble.com","bilibili.com","b23.tv","triller.co","mojapp.in","joshapp.com","joshapp.in","myjosh.in","joshapp.net","share.myjosh.in","chingari.io","sharechat.com","kooapp.com","roposo.com","public.com","mitron.tv"}
def host(u):
    try:return urlparse(u).netloc.lower().split(':')[0].removeprefix('www.')
    except:return ''
def allowed(u):
    h=host(u); return any(h==d or h.endswith('.'+d) for d in DOMAINS)
def kind(x):
    mime=(x.get('mime_type') or '').lower(); ext=(x.get('ext') or '').lower(); u=(x.get('url') or '').lower()
    if (mime.startswith('video/') or ext in {'mp4','webm','mov','m4v','flv','mkv','ts'} or '.m3u8' in u or '.mp4' in u or 'video.twimg.com/' in u or 'cdninstagram.com/' in u or 'fbcdn.net/' in u or 'pinimg.com/videos/' in u or 'v.redd.it/' in u or 'sc-cdn.net/' in u or 'telesco.pe/' in u or 'licdn.com/' in u or 'myjosh.in/' in u or 'mojapp.in/' in u or 'sharechat.com/' in u):return 'video'
    if mime.startswith('image/') or ext in {'jpg','jpeg','png','webp','gif','avif'}:return 'photo'
    return 'media'
def collect(info):
    out=[]
    def walk(x):
        if not isinstance(x,dict):return
        if x.get('url'):out.append({'type':kind(x),'url':x['url'],'ext':x.get('ext'),'format_id':x.get('format_id'),'mime_type':x.get('mime_type'),'width':x.get('width'),'height':x.get('height')})
        for y in x.get('entries') or []:walk(y)
    walk(info); seen=set(); r=[]
    for x in out:
        if x['url'] not in seen:seen.add(x['url']);r.append(x)
    return r
@app.get('/')
def home():return jsonify(status='online',service='VixRola Universal Video API',version='4',engine='yt-dlp')
@app.get('/health')
def health():return jsonify(status='ok',version='4')
@app.route('/download',methods=['GET','POST'])
def download():
    u=request.args.get('url')
    if not u and request.is_json:u=(request.get_json(silent=True) or {}).get('url')
    if not u:return jsonify(status='error',message='URL is required.'),400
    if not allowed(u):return jsonify(status='error',message='This domain is not enabled.'),400
    opts={'quiet':True,'no_warnings':True,'skip_download':True,'extract_flat':False,'noplaylist':False,'socket_timeout':30,'retries':2}
    try:
        with yt_dlp.YoutubeDL(opts) as y:info=y.extract_info(u,download=False)
        media=collect(info); videos=[m for m in media if m['type']=='video']
        if not videos:return jsonify(status='error',message='No accessible video media was returned by yt-dlp.'),422
        def score(m):
            s=0; url=m['url'].lower()
            if m.get('ext')=='mp4':s+=50
            if '.m3u8' not in url:s+=20
            if m.get('height'):s+=min(int(m['height']),2160)/1000
            return s
        videos.sort(key=score,reverse=True)
        return jsonify(status='success',platform=host(u),title=info.get('title') or info.get('description') or 'Video',media_type='video',download_url=videos[0]['url'],media=videos,count=len(videos))
    except yt_dlp.utils.DownloadError as e:return jsonify(status='error',platform=host(u),message='yt-dlp could not extract this video.',details=str(e)),422
    except Exception as e:app.logger.exception('Extraction failed');return jsonify(status='error',platform=host(u),message='Extraction failed.',details=str(e)),500
if __name__=='__main__':app.run(host='0.0.0.0',port=5000)
