# VixRola Universal Media Extraction API

A fast, lightweight media extraction API and live web console powered by Node.js and yt-dlp.

## Supported Domains
Instagram, Facebook, X (Twitter), Pinterest, Reddit, Snapchat, Telegram, LinkedIn, Moj, Josh, YouTube, TikTok, Threads, Discord, Tumblr, Vimeo, Dailymotion, Twitch, and more.

## API Endpoints

- `GET /` - Service status or interactive web test console
- `GET /health` - Healthcheck & yt-dlp version info
- `GET /download?url={video_url}` - Extract video streams and download link
- `POST /download` - Extract via JSON body: `{"url": "https://..."}`

## Installation & Running Locally

```bash
# Install dependencies (automatically sets up yt-dlp)
npm install

# Start development server
npm run dev

# Start production server
npm start
```

## Deployment (Render / Railway / VPS / Cloud Run)

- **Build Command**: `npm install`
- **Start Command**: `npm start`
- **Port**: `3000` (or set via `PORT` environment variable)
