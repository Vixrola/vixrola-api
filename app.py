from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'online', 'message': 'VixRola API is running'})

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
        # Cobalt API Call
        cobalt_url = "https://co.wuk.sh/api/json"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "vQuality": "1080"
        }
        
        response = requests.post(cobalt_url, json=payload, headers=headers, timeout=15)
        res_data = response.json()
        
        if response.status_code == 200 and res_data.get('url'):
            return jsonify({
                'status': 'success',
                'title': 'VixRola Extracted HD Video',
                'thumbnail': 'https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?auto=format&fit=crop&w=600&q=80',
                'downloadUrl': res_data['url'],
                'quality': '1080p HD'
            })
        else:
            return jsonify({'status': 'error', 'message': 'Could not extract MP4 video.'}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
