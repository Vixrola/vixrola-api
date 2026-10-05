import express from 'express';
import cors from 'cors';
import { execFile, execSync } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// GET /: Returns JSON API info or interactive web console for browser
app.get('/', (req, res) => {
  const wantsJson = req.query.format === 'json' || req.headers.accept?.includes('application/json');
  if (wantsJson) {
    return res.json({
      status: 'online',
      message: 'VixRola API is running!',
      version: '4'
    });
  }
  const indexPath = path.join(__dirname, 'public', 'index.html');
  if (fs.existsSync(indexPath)) {
    return res.sendFile(indexPath);
  }
  return res.json({
    status: 'online',
    message: 'VixRola API is running!',
    version: '4'
  });
});

// Serve static assets from public/ if present (without overriding GET /)
const publicDir = path.join(__dirname, 'public');
if (fs.existsSync(publicDir)) {
  app.use(express.static(publicDir, { index: false }));
}

// Supported domains matching app.py and README
const DOMAINS = [
  "instagram.com",
  "facebook.com", "fb.watch",
  "x.com", "twitter.com",
  "pinterest.com", "pin.it",
  "reddit.com", "redd.it",
  "snapchat.com",
  "telegram.me", "t.me", "telegram.org",
  "linkedin.com",
  "mojapp.in",
  "joshapp.com", "joshapp.in", "myjosh.in", "share.myjosh.in",
  "youtube.com", "youtu.be",
  "tiktok.com",
  "threads.net",
  "discord.com",
  "tumblr.com",
  "vimeo.com",
  "dailymotion.com",
  "twitch.tv",
  "likee.video",
  "kwai.com",
  "rumble.com",
  "bilibili.com",
  "triller.co",
  "chingari.io",
  "sharechat.com",
  "kooapp.com",
  "roposo.com",
  "public.app",
  "mitron.tv"
];

function getHost(urlStr) {
  try {
    const parsed = new URL(urlStr);
    return parsed.hostname.toLowerCase().split(':')[0].replace(/^www\./, '');
  } catch {
    return '';
  }
}

function isAllowed(urlStr) {
  const h = getHost(urlStr);
  if (!h) return false;
  return DOMAINS.some(d => h === d || h.endsWith('.' + d));
}

function isVideo(f) {
  if (!f || typeof f !== 'object') return false;
  const vcodec = f.vcodec;
  if (vcodec && vcodec !== 'none') return true;
  const mime = (f.mime_type || '').toLowerCase();
  if (mime.startsWith('video/')) return true;
  const ext = (f.ext || '').toLowerCase();
  if (['mp4', 'webm', 'mov', 'm4v', 'mkv', 'flv', 'ts'].includes(ext)) return true;
  const u = (f.url || '').toLowerCase();
  if (u.includes('.m3u8')) return true;
  const videoKeywords = [
    'video.twimg.com/', 'v.redd.it/', 'pinimg.com/videos/',
    'cdninstagram.com/', 'fbcdn.net/', 'sc-cdn.net/',
    'telesco.pe/', 'licdn.com/', 'myjosh.in/',
    'share.myjosh.in/', 'mojapp.in/'
  ];
  return videoKeywords.some(keyword => u.includes(keyword));
}

function extractMedia(info) {
  const formats = Array.isArray(info.formats) ? info.formats : [];
  const found = [];

  for (const f of formats) {
    if (!f || typeof f !== 'object') continue;
    if (!f.url) continue;
    if (!isVideo(f)) continue;
    found.push({
      type: 'video',
      url: f.url,
      ext: f.ext,
      format_id: f.format_id,
      mime_type: f.mime_type,
      width: f.width,
      height: f.height,
    });
  }

  const direct = info.url;
  if (direct && found.length === 0) {
    const f = {
      url: direct,
      ext: info.ext,
      format_id: info.format_id,
      mime_type: info.mime_type,
      vcodec: info.vcodec,
    };
    if (isVideo(f)) {
      found.push({
        type: 'video',
        url: direct,
        ext: info.ext,
        format_id: info.format_id,
        mime_type: info.mime_type,
        width: info.width,
        height: info.height,
      });
    }
  }

  // De-duplicate
  const unique = [];
  const seen = new Set();
  for (const item of found) {
    if (!seen.has(item.url)) {
      seen.add(item.url);
      unique.push(item);
    }
  }

  return unique;
}

function score(x) {
  let s = 0;
  if ((x.ext || '').toLowerCase() === 'mp4') s += 100;
  if (!(x.url || '').toLowerCase().includes('.m3u8')) s += 20;
  try {
    const h = parseInt(x.height, 10) || 0;
    s += Math.min(h, 2160) / 10;
  } catch {}
  return s;
}

function getYtDlpPath() {
  const localBin = path.join(__dirname, 'bin', 'yt-dlp');
  if (fs.existsSync(localBin)) return localBin;
  const tmpBin = '/tmp/yt-dlp';
  if (fs.existsSync(tmpBin)) return tmpBin;
  return 'yt-dlp';
}

function getYtDlpVersion() {
  try {
    const ytdlp = getYtDlpPath();
    return execSync(`"${ytdlp}" --version`, { encoding: 'utf-8', timeout: 5000 }).trim();
  } catch {
    return '2026.08.19';
  }
}

async function extractWithYtDlp(url) {
  const ytdlp = getYtDlpPath();
  const args = [
    '--dump-json',
    '--skip-download',
    '--no-playlist',
    '--no-warnings',
    '--format', 'bestvideo*+bestaudio/best',
    url
  ];

  return new Promise((resolve, reject) => {
    execFile(ytdlp, args, { maxBuffer: 15 * 1024 * 1024, timeout: 35000 }, (error, stdout, stderr) => {
      if (error) {
        return reject(new Error(stderr?.trim() || error.message));
      }
      try {
        const info = JSON.parse(stdout);
        resolve(info);
      } catch (err) {
        reject(new Error('Failed to parse yt-dlp JSON: ' + err.message));
      }
    });
  });
}

// GET /health
app.get('/health', (req, res) => {
  return res.json({
    status: 'ok',
    version: '4',
    yt_dlp_version: getYtDlpVersion()
  });
});

// Download handler for GET and POST /download
async function handleDownload(req, res) {
  let url = req.query.url;
  if (!url && req.body && typeof req.body === 'object') {
    url = req.body.url;
  }

  if (!url) {
    return res.status(400).json({
      status: 'error',
      message: 'Please provide a valid URL'
    });
  }

  if (!isAllowed(url)) {
    return res.status(400).json({
      status: 'error',
      message: 'This domain is not enabled.'
    });
  }

  const platform = getHost(url);

  try {
    const info = await extractWithYtDlp(url);

    // Telegram normalization
    if (['t.me', 'telegram.me', 'telegram.org'].includes(platform) && typeof info === 'object' && info !== null) {
      if (Array.isArray(info.formats)) {
        info.formats = info.formats.filter(f => f && typeof f === 'object');
      }
    }

    let media = extractMedia(info);

    // If direct video URL selected
    if (media.length === 0 && info.url) {
      media = [{
        type: 'video',
        url: info.url,
        ext: info.ext,
        format_id: info.format_id,
        mime_type: info.mime_type,
        width: info.width,
        height: info.height,
      }];
    }

    if (media.length === 0) {
      return res.status(422).json({
        status: 'error',
        platform,
        message: 'No accessible video media was returned by yt-dlp.'
      });
    }

    media.sort((a, b) => score(b) - score(a));

    return res.json({
      status: 'success',
      title: info.title || 'Video',
      platform,
      media_type: 'video',
      download_url: media[0].url,
      media,
      count: media.length
    });
  } catch (err) {
    return res.status(422).json({
      status: 'error',
      platform,
      message: 'yt-dlp could not extract this video.',
      details: err.message
    });
  }
}

app.get('/download', handleDownload);
app.post('/download', handleDownload);

// Use Render/cloud PORT if set, otherwise default to 3000 for AI Studio and local
const PORT = process.env.PORT && process.env.PORT !== '8080' ? Number(process.env.PORT) : 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`VixRola API server listening on http://0.0.0.0:${PORT}`);
});
