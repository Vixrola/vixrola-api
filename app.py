from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os

app = FastAPI(title="Media Downloader API")

# आपकी वेबसाइट/फ्रंटएंड से बिना किसी CORS एरर के कॉल करने के लिए
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_cookie_path():
    """Render की Secret File या लोकल cookies.txt चेक करता है"""
    if os.path.exists("/etc/secrets/cookies.txt"):
        return "/etc/secrets/cookies.txt"
    elif os.path.exists("cookies.txt"):
        return "cookies.txt"
    return None

@app.get("/")
def home():
    cookie_status = "Available" if get_cookie_path() else "Not Found"
    return {
        "status": "Online",
        "message": "Media Downloader API is running smoothly!",
        "cookies_status": cookie_status
    }

@app.get("/extract")
def extract_video_info(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    cookie_file = get_cookie_path()

    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web_embedded']
            }
        }
    }

    # अगर Render पर Secret File मिली, तो उसे जोड़ें
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # डायरेक्ट मीडिया URL प्राप्त करें
            download_url = info.get('url')
            if not download_url and 'formats' in info:
                # अगर डायरेक्ट url न मिले तो बेस्ट फॉर्मेट चुनें
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
