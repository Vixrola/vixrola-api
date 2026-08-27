# VixRola Universal yt-dlp API — Webshare Proxy Rotation

Universal Flask + yt-dlp API for the supported domains in `app.py`.

## Webshare proxy rotation

Configure up to 10 Webshare proxies in Render Environment Variables:

```text
WEBSHARE_PROXY_1
WEBSHARE_PROXY_2
WEBSHARE_PROXY_3
WEBSHARE_PROXY_4
WEBSHARE_PROXY_5
WEBSHARE_PROXY_6
WEBSHARE_PROXY_7
WEBSHARE_PROXY_8
WEBSHARE_PROXY_9
WEBSHARE_PROXY_10
```

Each value should be a complete proxy URL, for example:

```text
http://USERNAME:PASSWORD@HOST:PORT
```

Do not commit proxy usernames/passwords to GitHub. Store them only as Render Environment Variables.

### Rotation behavior

- Round-robin selection across configured proxies.
- A request uses one proxy for the extraction attempt.
- If yt-dlp fails or returns no usable media, that proxy is placed in cooldown and the next available proxy is tried.
- Default failed-proxy cooldown: **300 seconds (5 minutes)**.
- Change it with `PROXY_COOLDOWN_SECONDS` if needed.
- A successful proxy is immediately available again.
- A single request tries each currently available proxy at most once.
- If all proxies are in cooldown, the API returns HTTP `503` rather than bypassing the configured proxy pool.

### Backward compatibility

If no `WEBSHARE_PROXY_1` ... `WEBSHARE_PROXY_10` variables are configured, the API will use the existing `YTDLP_PROXY` variable if present. If neither is configured, yt-dlp connects directly.

## Health check

Open:

```text
https://YOUR-RENDER-SERVICE.onrender.com/health
```

It reports only proxy counts/status; proxy credentials are never returned.

Example:

```json
{
  "status": "ok",
  "proxy_pool": {
    "configured": true,
    "total": 10,
    "active": 8,
    "cooldown": 2,
    "cooldown_seconds": 300
  }
}
```

## Render

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
gunicorn app:app --bind 0.0.0.0:$PORT
```

The included `Procfile` contains the same start command.

## Supported domains

Facebook, Instagram, YouTube, TikTok, X/Twitter, Snapchat, Telegram,
Pinterest, LinkedIn, Reddit, Threads, Discord, Tumblr, Vimeo, Dailymotion,
Twitch, Likee, Kwai, Rumble, Bilibili, Triller, Moj, Josh, Chingari,
ShareChat, Koo, Roposo, Public and Mitron.

A domain being listed does not guarantee every URL/content type is supported by the current yt-dlp release. Private, login-required, DRM-protected, expired or restricted content cannot be bypassed.
