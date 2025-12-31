# hls_converter.py
import subprocess
import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

HLS_DIR = "streams/hls"

def convert_to_hls(input_url, output_dir):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    master_file = os.path.join(output_dir, "master.m3u8")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_url,          # input URL or local path
        "-c:v", "copy",
        "-c:a", "copy",
        "-c:s", "webvtt",
        "-f", "hls",
        "-hls_time", "6",
        "-hls_list_size", "0",
        "-hls_flags", "independent_segments",
        "-hls_segment_filename",
        f"{output_dir}/seg_%03d.ts",
        master_file
    ]

    subprocess.run(cmd, check=True)
    return master_file

@app.route("/convert_hls", methods=["POST"])
def convert_hls_endpoint():
    data = request.get_json()
    video_url = data.get("video_url")

    if not video_url:
        return jsonify({"error": "No video_url provided"}), 400

    # Create unique folder name based on filename
    filename = video_url.split("/")[-1].split("?")[0]
    output_dir = os.path.join(HLS_DIR, filename)

    if not os.path.exists(os.path.join(output_dir, "master.m3u8")):
        try:
            convert_to_hls(video_url, output_dir)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Return HLS link
    hls_link = f"/hls/{filename}/master.m3u8"
    return jsonify({"hls_link": hls_link})

@app.route("/hls/<path:folder>/<path:file>")
def serve_hls(folder, file):
    return send_from_directory(os.path.join(HLS_DIR, folder), file)

if __name__ == "__main__":
    os.makedirs(HLS_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
