# VixRola — 7-platform test backend + Webshare proxy rotation

This is an updated test build of the existing VixRola Flask + yt-dlp backend.
The existing platform/domain and extraction logic is preserved, with a Webshare
proxy pool added for testing.

## Webshare proxy setup on Render

Add up to 10 Render Environment Variables:

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

Each value should be a complete proxy URL supplied by Webshare, for example:

```text
http://USERNAME:PASSWORD@HOST:PORT
```

Do not commit proxy credentials to GitHub.

### Optional settings

```text
PROXY_COOLDOWN_SECONDS=300
YTDLP_COOKIES_FILE=/path/to/cookies.txt
```

`PROXY_COOLDOWN_SECONDS` defaults to 300 seconds (5 minutes).

For backward compatibility, if no `WEBSHARE_PROXY_*` variables are configured,
the old single-proxy variable is still supported:

```text
YTDLP_PROXY=http://USERNAME:PASSWORD@HOST:PORT
```

## Rotation behavior

When the Webshare pool is configured, `/download` selects proxies in round-robin
order. If extraction through a proxy raises an error, that proxy is placed in
cooldown and another available proxy is tried. A successful proxy is removed
from cooldown and can be selected again normally.

The pool is process-local. On a multi-instance deployment, each instance has
its own in-memory rotation state.

## Health check

Open:

```text
GET /health
```

The response reports the configured pool size, currently available proxies,
cooldown count, yt-dlp version, and whether cookies are configured. Proxy
credentials themselves are never returned.

## Deploy on Render

The included `Procfile` is kept for the existing deployment. Typical start command:

```text
gunicorn app:app
```

## Important testing note

The free Webshare proxy pool may contain datacenter/shared IPs and may not work
reliably with every social platform. Proxy rotation is a retry mechanism, not a
guarantee that a platform will permit extraction. Respect each platform's terms
and only process content you are authorized to access.
