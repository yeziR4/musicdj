from flask import Flask, jsonify, request, send_from_directory
import requests

app = Flask(__name__)

# RapidAPI details
RAPIDAPI_DOWNLOAD_URL = "https://spotify-downloader9.p.rapidapi.com/downloadSong"


# Route to serve the frontend
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# Route for API: Fetch playlists
@app.route("/playlists", methods=["GET"])
def get_playlists():
    access_token = request.headers.get("Authorization")
    if not access_token:
        return jsonify({"error": "Access token is required!"}), 400

    response = requests.get(
        "https://api.spotify.com/v1/me/playlists",
        headers={"Authorization": access_token},
    )
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch playlists!"}), 400

    playlists = response.json()
    return jsonify(playlists)

# Route for API: Download track
@app.route("/download-track", methods=["GET"])
def download_track():
    track_id = request.args.get("track_id")
    if not track_id:
        return jsonify({"error": "Track ID is required!"}), 400

    response = requests.get(
        RAPIDAPI_DOWNLOAD_URL,
        headers={
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "spotify-downloader9.p.rapidapi.com",
        },
        params={"songId": track_id},
    )
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch download link!"}), 400

    data = response.json()
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
