from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)

# CORS इनेबल करना बहुत ज़रूरी है ताकि वेबसाइट से रिक्वेस्ट ब्लॉक ना हो
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'online', 'message': 'VixRola API is running!'})

# वेबसाइट जिन-जिन रास्तों से रिक्वेस्ट भेज सकती है, वो सब यहाँ जोड़ दिए गए हैं
@app.route('/download', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/analyze', methods=['POST', 'OPTIONS'])
@app.route('/api/analyze', methods=['POST', 'OPTIONS'])
@app.route('/api/download', methods=['POST', 'OPTIONS'])
@app.route('/extract', methods=['POST', 'OPTIONS'])
@app.route('/api/extract', methods=['POST', 'OPTIONS'])
def process_video():
    # OPTIONS रिक्वेस्ट (CORS Preflight) को तुरंत पास करें
    if request.method == 'OPTIONS':
        return '', 200

    url = request.args.get('url')
    if not url and request.is_json:
        data = request.get_json()
        url = data.get('url') if data else None
        
    if not url:
        return jsonify({'status': 'error', 'message': 'Please provide a valid URL'}), 400

    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')
            thumbnail = info.get('thumbnail', 'https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7')
            
            return jsonify({
                'status': 'success',
                'title': info.get('title', 'VixRola Extracted Video'),
                'thumbnail': thumbnail,
                'downloadUrl': video_url,
                'quality': '1080p HD'
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
