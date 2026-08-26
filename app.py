from fastapi import FastAPI, HTTPException
import yt_dlp

app = FastAPI(title="Media Downloader API")

@app.get("/extract")
def extract_video_info(url: str):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        # Bot detection bypass
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web_embedded']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "success": True,
                "title": info.get('title'),
                "thumbnail": info.get('thumbnail'),
                "download_url": info.get('url'),
                "platform": info.get('extractor_key')
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
