from flask import Flask, jsonify, request, send_file, redirect, url_for,send_from_directory
import requests
import os
import json
import http.client
import google.generativeai as genai
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging

# Initialize Flask app
app = Flask(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Spotify API credentials
SPOTIFY_CLIENT_ID = os.getenv("CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("REDIRECT_URI")

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIFY_CLIENT_ID,
                                               client_secret=SPOTIFY_CLIENT_SECRET,
                                               redirect_uri=SPOTIFY_REDIRECT_URI,
                                               scope="user-library-read"))

# RapidAPI details
RAPIDAPI_DOWNLOAD_URL = "https://spotify-downloader9.p.rapidapi.com/downloadSong"
RAPIDAPI_HEADERS = {
    'x-rapidapi-key': "ddcf2a8d79msh5fd641f22600767p1d343bjsna3c2e5ddcff1",
    'x-rapidapi-host': "spotify-downloader9.p.rapidapi.com"
}

# Helper Functions

def process_user_input(user_input):
    """Use Gemini to extract song/playlist details from user input."""
    try:
        response = model.generate_content(
            f"""Extract the song name and artist from this request: '{user_input}'
            Format the response exactly like this JSON:
            {{"song": "song name here", "artist": "artist name here", "playlist": null}}
            Only include the JSON, no other text."""
        )
        
        # Get the text from the response
        response_text = response.text
        
        # Clean the response text to ensure it's valid JSON
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:-3]  # Remove ```json and ``` if present
        
        # Parse the JSON
        parsed_response = json.loads(response_text)
        
        # Ensure all required keys are present
        required_keys = ['song', 'artist', 'playlist']
        for key in required_keys:
            if key not in parsed_response:
                parsed_response[key] = None
                
        return parsed_response
        
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error: {e}")
        logging.error(f"Response text: {response_text}")
        return {"song": None, "artist": None, "playlist": None}
    except Exception as e:
        logging.error(f"Error processing user input: {e}")
        return {"song": None, "artist": None, "playlist": None}

def get_song_id(song_name, artist_name):
    """Fetch song ID from Spotify API."""
    query = f"track:{song_name} artist:{artist_name}"
    results = sp.search(q=query, type="track", limit=1)
    if results["tracks"]["items"]:
        return results["tracks"]["items"][0]["id"]
    return None

def get_playlist_id(playlist_name):
    """Fetch playlist ID from Spotify API."""
    playlists = sp.current_user_playlists()
    for playlist in playlists["items"]:
        if playlist_name.lower() in playlist["name"].lower():
            return playlist["id"]
    return None

def download_song(song_id):
    """Download song using RapidAPI Spotify Downloader."""
    conn = http.client.HTTPSConnection("spotify-downloader9.p.rapidapi.com")
    conn.request("GET", f"/downloadSong?songId={song_id}", headers=RAPIDAPI_HEADERS)
    res = conn.getresponse()
    data = res.read()
    response_json = json.loads(data.decode("utf-8"))
    if response_json.get("success", False):
        download_link = response_json["data"]["downloadLink"]
        audio_response = requests.get(download_link)
        if audio_response.status_code == 200:
            with open(f"{song_id}.mp3", "wb") as f:
                f.write(audio_response.content)
            return True
    return False

def generate_dj_adlib(song_name, artist_name):
    """Generate DJ adlib using Gemini."""
    prompt = f"Generate a short and energetic DJ adlib for the song '{song_name}' by {artist_name}."
    response = model.generate_content(prompt)
    return response.text

# Flask Routes

@app.route("/auth/login", methods=["GET"])
def auth_login():
    """Redirect user to Spotify login page."""
    SCOPES = "playlist-read-private user-library-read"
    login_url = (
        f"https://accounts.spotify.com/authorize"
        f"?client_id={SPOTIFY_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
        f"&scope={SCOPES}"
    )
    return jsonify({"url": login_url})

@app.route("/callback", methods=["GET"])
def callback():
    """Handle Spotify callback and exchange code for access token."""
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Authorization code is missing!"}), 400

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        },
    )

    if response.status_code != 200:
        return jsonify({"error": "Failed to exchange token!"}), 400

    token_data = response.json()
    return redirect(
        url_for(
            "index",
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data["expires_in"],
        )
    )

@app.route("/request-song", methods=["POST"])
def request_song():
    try:
        user_input = request.json.get("input")
        if not user_input:
            return jsonify({"error": "User input is required!"}), 400

        # Step 1: Process user input
        processed_input = process_user_input(user_input)
        logging.debug(f"Processed input: {processed_input}")

        if not processed_input.get("song") or not processed_input.get("artist"):
            return jsonify({"error": "Could not extract song and artist information"}), 400

        # Step 2: Fetch song ID
        song_id = get_song_id(processed_input["song"], processed_input["artist"])
        if not song_id:
            return jsonify({"error": "Song not found!"}), 404

        # Step 3: Download the song
        if download_song(song_id):
            # Step 4: Generate DJ adlib
            adlib = generate_dj_adlib(processed_input["song"], processed_input["artist"])
            return jsonify({
                "song_id": song_id,
                "adlib": adlib,
                "download_link": f"/play/{song_id}"
            })
        else:
            return jsonify({"error": "Failed to download song!"}), 500

    except Exception as e:
        logging.error(f"Error in request_song: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route("/play/<song_id>", methods=["GET"])
def play_song(song_id):
    """Serve the downloaded song."""
    file_path = f"{song_id}.mp3"
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({"error": "Song not found!"}), 404

@app.route("/")
def index():
    """Serve the frontend."""
    return send_from_directory("static", "index.html")

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
