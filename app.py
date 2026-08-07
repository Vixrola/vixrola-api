from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)

# CORS चालू करना
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'online', 'message': 'VixRola API is running with Dual Bypass APIs!'})

@app.route('/download', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/analyze', methods=['POST', 'OPTIONS'])
@app.route('/api/analyze', methods=['POST', 'OPTIONS'])
@app.route('/api/download', methods=['POST', 'OPTIONS'])
def process_video():
    if request.method == 'OPTIONS':
        return '', 200

    url = request.args.get('url')
    if not url and request.is_json:
        data = request.get_json()
        url = data.get('url') if data else None
        
    if not url:
        return jsonify({'status': 'error', 'message': 'Please provide a valid URL'}), 400

    try:
        video_url = None
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # --- API 1: Siputzx (Instagram Downloader) ---
        try:
            api1 = f"https://api.siputzx.my.id/api/d/igdl?url={url}"
            resp1 = requests.get(api1, headers=headers, timeout=10).json()
            if resp1.get('status') == True and resp1.get('data'):
                for item in resp1['data']:
                    if item.get('url'):
                        video_url = item['url']
                        break
        except Exception:
            pass

        # --- API 2: AEMT (Backup API) ---
        if not video_url:
            try:
                api2 = f"https://aemt.me/download/igdl?url={url}"
                resp2 = requests.get(api2, headers=headers, timeout=10).json()
                if resp2.get('status') == True and resp2.get('result'):
                    video_url = resp2['result'][0]['url']
            except Exception:
                pass

        # अगर दोनों में से किसी भी API ने वीडियो लिंक दे दिया, तो उसे वेबसाइट पर भेज दो
        if video_url:
            return jsonify({
                'status': 'success',
                'title': 'VixRola Extracted HD Video',
                'thumbnail': 'https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?auto=format&fit=crop&w=600&q=80',
                'downloadUrl': video_url,
                'quality': '1080p HD'
            })
        else:
            return jsonify({'status': 'error', 'message': 'Could not extract MP4. The reel might be private.'}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Backend Processing Error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
