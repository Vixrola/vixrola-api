from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)

# CORS चालू करना ताकि वेबसाइट और सर्वर आपस में बात कर सकें
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'online', 'message': 'VixRola API is running with Free Bypass API!'})

@app.route('/download', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/analyze', methods=['POST', 'OPTIONS'])
@app.route('/api/analyze', methods=['POST', 'OPTIONS'])
@app.route('/api/download', methods=['POST', 'OPTIONS'])
@app.route('/extract', methods=['POST', 'OPTIONS'])
@app.route('/api/extract', methods=['POST', 'OPTIONS'])
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
        # Free API का इस्तेमाल कर रहे हैं (बिना किसी लॉगिन या ब्लॉक के काम करेगा)
        api_url = "https://api.cobalt.tools/api/json"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "vQuality": "1080"
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        response_data = response.json()
        
        video_url = None
        
        # API से वीडियो लिंक निकालना
        if response_data.get('status') == 'success' or response_data.get('url'):
            video_url = response_data.get('url')
        elif response_data.get('status') == 'picker':
            items = response_data.get('picker', [])
            if items and len(items) > 0:
                video_url = items[0].get('url')

        if video_url:
            return jsonify({
                'status': 'success',
                'title': 'VixRola Extracted HD Video',
                'thumbnail': 'https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?auto=format&fit=crop&w=600&q=80',
                'downloadUrl': video_url,
                'quality': '1080p HD'
            })
        else:
            return jsonify({'status': 'error', 'message': 'वीडियो नहीं मिल पाया। लिंक प्राइवेट हो सकता है।'}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Server Error: API काम नहीं कर रही है।'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
