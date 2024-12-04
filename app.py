import os
from flask import Flask, request, jsonify, redirect, url_for
import requests

app = Flask(__name__)

# Read environment variables
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"
RAPIDAPI_DOWNLOAD_URL = "https://spotify-downloader9.p.rapidapi.com/downloadSong"
RAPIDAPI_PLAYLIST_URL = "https://spotify-downloader9.p.rapidapi.com/downloadPlaylist"

@app.route("/")
def home():
    return "Welcome to Music DJ Backend!"

@app.route("/login")
def login():
    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=playlist-read-private"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Authorization code not found!"}), 400

    # Request access token from Spotify
    response = requests.post(
        SPOTIFY_AUTH_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    if response.status_code != 200:
        return jsonify({"error": "Failed to authenticate with Spotify!"}), 400

    data = response.json()
    access_token = data.get("access_token")

    # Optionally, save token in session or database
    return jsonify({"access_token": access_token})

@app.route("/get-playlists")
def get_playlists():
    access_token = request.args.get("access_token")
    if not access_token:
        return jsonify({"error": "Access token is required!"}), 400

    response = requests.get(
        f"{SPOTIFY_API_URL}/me/playlists",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch playlists!"}), 400

    playlists = response.json()
    return jsonify(playlists)

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
