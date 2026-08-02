from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'online', 'message': 'VixRola API is running!'})

@app.route('/download', methods=['GET', 'POST'])
def download_video():
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
            
            return jsonify({
                'status': 'success',
                'title': info.get('title', 'Video'),
                'download_url': video_url
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
  
