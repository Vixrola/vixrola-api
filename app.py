from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import shutil

app = FastAPI(title="VixRola Universal Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_cookie_file():
    """Render की Read-only फ़ाइल को /tmp में कॉपी करता है ताकि Write Error न आए"""
    secret_path = "/etc/secrets/cookies.txt"
    temp_path = "/tmp/cookies.txt"
    
    if os.path.exists(secret_path):
        try:
            shutil.copyfile(secret_path, temp_path)
            return temp_path
        except Exception:
            return secret_path
    elif os.path.exists("cookies.txt"):
        return "cookies.txt"
    return None

@app.get("/")
def home():
    secret_exists = os.path.exists("/etc/secrets/cookies.txt") or os.path.exists("cookies.txt")
    return {
        "status": "Online",
        "message": "VixRola Downloader API is running smoothly!",
        "cookies_status": "Available" if secret_exists else "Not Found"
    }

@app.get("/extract")
def extract_video_info(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    cookie_file = get_cookie_file()

    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'web_embedded', 'tv', 'android']
            }
        }
    }

    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            download_url = info.get('url')
            if not download_url and 'formats' in info:
                download_url = info['formats'][-1].get('url')

            return {
                "success": True,
                "title": info.get('title'),
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration'),
                "download_url": download_url,
                "platform": info.get('extractor_key')
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
