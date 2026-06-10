from flask import Flask, request, jsonify, send_from_directory
import os
from werkzeug.utils import secure_filename
from flask_cors import CORS

app = Flask(__name__, static_folder=None)
CORS(app)  # Allow requests from frontend

BASE_UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)

# Store metadata of the latest uploaded base file
latest_base = {}

@app.route('/api/upload_base', methods=['POST'])
def upload_base():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    filename = secure_filename(file.filename)
    file_path = os.path.join(BASE_UPLOAD_FOLDER, filename)
    file.save(file_path)
    global latest_base
    latest_base = {
        'name': filename,
        'url': f'/api/download_base/{filename}'
    }
    return jsonify(latest_base), 200

@app.route('/api/get_base', methods=['GET'])
def get_base():
    return jsonify(latest_base if latest_base else {}), 200

@app.route('/api/download_base/<filename>', methods=['GET'])
def download_base(filename):
    return send_from_directory(BASE_UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    # Run on port 5000; adjust host as needed for SharePoint deployment
    app.run(host='0.0.0.0', port=5000, debug=True)
