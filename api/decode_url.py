from flask import request, jsonify
from app import app
from googlenewsdecoder import GoogleNewsDecoder

@app.route('/decode_url', methods=['POST'])
def decode_url():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    try:
        decoder = GoogleNewsDecoder()
        decoded_url = decoder.decode(url)
        return jsonify({'decoded_url': decoded_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
