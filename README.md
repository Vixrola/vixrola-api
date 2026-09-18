VdZip Backend — fixed version
What was fixed
Audio-only .m3u8 entries are no longer blindly labelled as video.
/download remains a metadata/extraction endpoint.
New /download-file endpoint performs a real download.
yt-dlp can select best video + best audio and FFmpeg can merge them to MP4.
Retries, fragment retries and socket timeout were added.
Render's $PORT is respected.
Decodo proxy environment variables remain supported.
Important
For /download-file to merge separate video/audio streams (Pinterest, Reddit, X, etc.), the server must have FFmpeg installed.
Render
Use render.yaml or set: Build command: pip install -r requirements.txt Start command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180
If using a Python runtime without FFmpeg, use the included Dockerfile so FFmpeg is installed.
Endpoints
GET /health GET /download?url=... GET /download-file?url=... GET /proxy-test
POST JSON also works: {"url":"https://example.com/..."}
