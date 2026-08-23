# VixRola API

This Render backend supports extracting publicly accessible media that the
current yt-dlp Instagram/Facebook extractors can access.

## Deploy on Render

Build command:
    pip install -r requirements.txt

Start command:
    gunicorn app:app --bind 0.0.0.0:$PORT

## Endpoint

GET:
    /download?url=POST_URL

POST JSON:
    {"url": "POST_URL"}

The response includes:
- download_url: first media URL (keeps compatibility with the old frontend)
- media: list of extracted media
- media_type: photo/video
- count, video_count, photo_count

## Important limitations

A backend cannot bypass Instagram/Facebook privacy, login, expired URLs,
rate limits, or access restrictions. Private accounts and many Stories/DP
requests may require authentication and may not be extractable by yt-dlp.
Do not add or use someone else's session cookies without authorization.

For carousel posts, the API returns multiple media items when the extractor
provides them.
