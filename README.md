VixRola Universal yt-dlp API
Enabled domains: Facebook, Instagram, YouTube, TikTok, X/Twitter, Snapchat, Telegram, Pinterest, LinkedIn, Reddit, Threads, Discord, Tumblr, Vimeo, Dailymotion, Twitch, Likee, Kwai, Rumble, Bilibili, Triller, Moj, Josh, Chingari, ShareChat, Koo, Roposo, Public and Mitron.
A domain being listed does not guarantee every URL/content type is supported by the current yt-dlp release. Private, login-required, DRM-protected, expired or restricted content cannot be bypassed.
Render: Build: pip install -r requirements.txt Start: gunicorn app:app --bind 0.0.0.0:$PORT
Decodo Residential Proxy on Render
Set these Environment Variables in your Render service:
DECODO_HOST = your Decodo proxy host
DECODO_PORT = 10001 (or the port provided by Decodo)
DECODO_USERNAME = your Decodo username
DECODO_PASSWORD = your Decodo password
Do not put the username/password in source code or commit them to GitHub.
The backend reads these variables at runtime and passes the resulting proxy to yt-dlp. If the Decodo variables are not configured, yt-dlp runs without a proxy.
Example Render values:
DECODO_HOST=your-decodo-host
DECODO_PORT=10001
DECODO_USERNAME=your-username
DECODO_PASSWORD=your-password
Keep your real credentials private.
Decodo Proxy Test
After deployment open /proxy-test. A successful response shows proxy_configured: true and the proxy IP.
Platform + Decodo update
The /download endpoint passes the configured Decodo residential proxy to yt-dlp. TikTok, Dailymotion (dailymotion.com, dai.ly) and YouTube (youtube.com, youtu.be) are enabled in the domain allowlist.
After deployment, verify:
/health
/proxy-test
Then test a public TikTok, Dailymotion, and YouTube URL. Platform availability can still vary with yt-dlp changes, authentication, regional restrictions, rate limits, or DRM.
V2 Platform/Proxy Update
Decodo proxy is passed to yt-dlp through the DECODO_* environment variables.
More robust yt-dlp format selection: bv*+ba/b.
Adds curl-cffi for yt-dlp browser impersonation support required by some extractors.
Keeps /health and /proxy-test.
Render Environment Variables remain:
DECODO_HOST
DECODO_PORT
DECODO_USERNAME
DECODO_PASSWORD
After deployment, verify /health, /proxy-test, then test TikTok, Dailymotion and YouTube public URLs.
