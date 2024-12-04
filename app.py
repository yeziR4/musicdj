from flask import Flask, jsonify, request, send_from_directory
import requests
import os

app = Flask(__name__)

# RapidAPI details
RAPIDAPI_DOWNLOAD_URL = "https://spotify-downloader9.p.rapidapi.com/downloadSong"

@app.route("/auth/login", methods=["GET"])
def auth_login():
    CLIENT_ID = os.getenv("CLIENT_ID")
    REDIRECT_URI = os.getenv("REDIRECT_URI")
    SCOPES = "playlist-read-private user-library-read"

    if not CLIENT_ID or not REDIRECT_URI:
        return jsonify({"error": "Missing CLIENT_ID or REDIRECT_URI in environment variables!"}), 500

    login_url = (
        f"https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES}"
    )
    return jsonify({"url": login_url})

@app.route("/callback", methods=["GET"])
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Authorization code is missing!"}), 400

    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    REDIRECT_URI = os.getenv("REDIRECT_URI")

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )

    if response.status_code != 200:
        return jsonify({"error": "Failed to exchange token!"}), 400

    token_data = response.json()
    return jsonify(token_data)

@app.route("/playlists", methods=["GET"])
def get_playlists():
    access_token = request.headers.get("Authorization")
    if not access_token:
        return jsonify({"error": "Access token is required!"}), 400

    response = requests.get(
        "https://api.spotify.com/v1/me/playlists",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch playlists!"}), 400

    return jsonify(response.json())

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(debug=True)
