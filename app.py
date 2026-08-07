from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

def is_valid_mp4(url):
    if not url:
        return False
    if 'instagram.com/reel/' in url or 'instagram.com/p/' in url:
        return False
    return True

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'online', 'message': 'VixRola Backend API is running!'})

@app.route('/download', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/download', methods=['POST', 'OPTIONS'])
@app.route('/analyze', methods=['POST', 'OPTIONS'])
@app.route('/api/analyze', methods=['POST', 'OPTIONS'])
def process_video():
    if request.method == 'OPTIONS':
        return '', 200

    url = request.args.get('url')
    if not url and request.is_json:
        data = request.get_json()
        url = data.get('url') if data else None

    if not url:
        return jsonify({'status': 'error', 'message': 'Please provide a valid URL'}), 400

    video_url = None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # API 1: Ryzendesu
    try:
        r1 = requests.get(f"https://api.ryzendesu.vip/api/downloader/igdl?url={url}", headers=headers, timeout=10).json()
        if r1.get('data'):
            for item in r1['data']:
                if item.get('url') and is_valid_mp4(item['url']):
                    video_url = item['url']
                    break
    except Exception:
        pass

    # API 2: Siputzx (Backup)
    if not video_url:
        try:
            r2 = requests.get(f"https://api.siputzx.my.id/api/d/igdl?url={url}", headers=headers, timeout=10).json()
            if r2.get('data'):
                for item in r2['data']:
                    if item.get('url') and is_valid_mp4(item['url']):
                        video_url = item['url']
                        break
        except Exception:
            pass

    if video_url:
        return jsonify({
            'status': 'success',
            'downloadUrl': video_url,
            'download_url': video_url,
            'title': 'VixRola Extracted HD Video',
            'thumbnail': 'https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?auto=format&fit=crop&w=600&q=80'
        })
    else:
        return jsonify({'status': 'error', 'message': 'Direct MP4 stream not found.'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
