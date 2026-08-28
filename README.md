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
