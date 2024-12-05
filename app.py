
from flask import Flask, jsonify, request, send_from_directory
import requests
import os
from flask import redirect, url_for
import logging
import sys


app = Flask(__name__)

# RapidAPI details
RAPIDAPI_DOWNLOAD_URL = "https://spotify-downloader9.p.rapidapi.com/downloadSong"

@app.route("/auth/login", methods=["GET"])
def auth_login():
    CLIENT_ID = os.getenv("CLIENT_ID")
    REDIRECT_URI = os.getenv("REDIRECT_URI")
    SCOPES = "playlist-read-private user-library-read"

    if not CLIENT_ID or not REDIRECT_URI:
        return jsonify({"error": "Missing CLIENT_ID or REDIRECT_URI in environment variables!!!"}), 500

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

    # Print out environment variables for debugging
    print(f"CLIENT_ID: {bool(CLIENT_ID)}")
    print(f"CLIENT_SECRET: {bool(CLIENT_SECRET)}")
    print(f"REDIRECT_URI: {REDIRECT_URI}")

    # Rest of the code remains the same

    

    # Exchange the authorization code for an access token
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

    # Redirect to the index page or another frontend-rendered route with the token
    return redirect(
        url_for(
            "index",  # This should match the function name of your frontend-rendered route
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data["expires_in"],
        )
    )




@app.route("/playlists/daily-mix", methods=["GET"])
def get_daily_mix_or_any_playlist():
    # Add logging
    print("Received headers:", request.headers)
    access_token = request.headers.get("Authorization")
    print(f"Extracted access token: {access_token}")

    if not access_token:
        print("No access token found!")
        return jsonify({"error": "Access token is required!"}), 400

    try:
        # More explicit token formatting
        spotify_headers = {"Authorization": f"Bearer {access_token}"}
        print("Spotify headers:", spotify_headers)

        # Fetch playlists from Spotify
        response = requests.get(
            "https://api.spotify.com/v1/me/playlists",
            headers=spotify_headers,
        )
        
        print("Spotify response status:", response.status_code)
        print("Spotify response body:", response.text)

        if response.status_code != 200:
            return jsonify({
                "error": f"Failed to fetch playlists. Status: {response.status_code}",
                "response": response.text
            }), 400
        playlists = response.json()
        
        # Debugging: print playlists to understand the structure
        print("Playlists:", playlists)
        
        # Look for "Daily Mix" playlist
        daily_mix = next(
            (playlist for playlist in playlists.get("items", []) if "Daily Mix" in playlist["name"]),
            None,
        )

        # If no "Daily Mix" found, use the first playlist
        selected_playlist = daily_mix or (playlists.get("items")[0] if playlists.get("items") else None)
        if not selected_playlist:
            return jsonify({"error": "No playlists available!!"}), 404

        # Fetch tracks for the selected playlist
        playlist_id = selected_playlist["id"]
        tracks_response = requests.get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if tracks_response.status_code != 200:
            return jsonify({"error": f"Failed to fetch tracks. Spotify responded with {tracks_response.status_code}. Response: {tracks_response.text}"}), 400

        tracks = tracks_response.json()

        # Extract relevant track details
        formatted_tracks = [
            {
                "title": track["track"]["name"],
                "artist": ", ".join(artist["name"] for artist in track["track"]["artists"]),
                "downloadLink": None,
            }
            for track in tracks.get("items", [])
        ]

        playlist_name = selected_playlist["name"]
        return jsonify({"playlist_name": playlist_name, "tracks": formatted_tracks})

    except Exception as e:
        
        print(f"Exception occurred: {str(e)}")
        print("Traceback:", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(debug=True)
