import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.join(__dirname, '..');
const binDir = path.join(rootDir, 'bin');
const binPath = path.join(binDir, 'yt-dlp');

if (!fs.existsSync(binPath)) {
  console.log('[setup] Downloading standalone yt-dlp binary...');
  fs.mkdirSync(binDir, { recursive: true });
  try {
    execSync('curl -L -s https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ' + binPath, { stdio: 'inherit' });
    execSync('chmod +x ' + binPath);
    console.log('[setup] yt-dlp installed successfully.');
  } catch (err) {
    console.warn('[setup] Could not download yt-dlp via curl, system PATH will be used:', err.message);
  }
} else {
  console.log('[setup] yt-dlp binary already present.');
}
