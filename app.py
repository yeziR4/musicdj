from flask import Flask, jsonify, request, send_file, redirect, url_for, send_from_directory
import requests
import os
import json
import http.client
import google.generativeai as genai
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

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

# Log environment variables status
logging.info("=== Checking Environment Variables ===")
logging.info(f"GEMINI_API_KEY set: {bool(GEMINI_API_KEY)}")
logging.info(f"SPOTIFY_CLIENT_ID set: {bool(SPOTIFY_CLIENT_ID)}")
logging.info(f"SPOTIFY_CLIENT_SECRET set: {bool(SPOTIFY_CLIENT_SECRET)}")
logging.info(f"SPOTIFY_REDIRECT_URI set: {bool(SPOTIFY_REDIRECT_URI)}")

# Initialize Spotify client
try:
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="user-library-read"
    ))
    # Test Spotify connection
    playlists = sp.current_user_playlists(limit=1)
    logging.info("Successfully connected to Spotify API")
except Exception as e:
    logging.error(f"Failed to initialize Spotify client: {str(e)}")
    # Don't raise the exception, let the app continue running

# RapidAPI details
RAPIDAPI_DOWNLOAD_URL = "https://spotify-downloader9.p.rapidapi.com/downloadSong"
RAPIDAPI_HEADERS = {
    'x-rapidapi-key': "ddcf2a8d79msh5fd641f22600767p1d343bjsna3c2e5ddcff1",
    'x-rapidapi-host': "spotify-downloader9.p.rapidapi.com"
}

from spotipy.oauth2 import SpotifyClientCredentials

# Initialize Spotify client with client credentials flow instead of OAuth
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    ))
    logging.info("Successfully initialized Spotify client with client credentials")
except Exception as e:
    logging.error(f"Failed to initialize Spotify client: {str(e)}")


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

import re

def fix_json(response_text):
    """Attempt to fix malformed JSON."""
    try:
        # Remove any non-JSON characters (e.g., markdown code blocks)
        response_text = re.sub(r'```json|```', '', response_text).strip()
        # Parse the JSON to ensure it's valid
        json.loads(response_text)
        return response_text
    except json.JSONDecodeError:
        # If the JSON is still invalid, return None
        return None

def process_user_input(user_input):
    logging.info(f"Processing user input: {user_input}")
    
    try:
        # Create the prompt
        prompt = f"""
        You are a music assistant integrated with the Spotify API. 
        The user has made the following request: '{user_input}'
        
        Your task is to:
        1. Understand the user's intent.
        2. Generate Python code to query the Spotify API and fetch the required song(s) or playlist.
        3. Return the code in the following format:
           ```python
           # Python code to query Spotify API
           results = sp.search(q="query", type="track", limit=1)
           song_id = results["tracks"]["items"][0]["id"]
           result = {{"songs": [song_id]}}
           ```
        
        Example 1:
        - User input: "Play Asake's latest song."
        - Output:
          ```python
          results = sp.search(q="artist:Asake", type="track", limit=1)
          song_id = results["tracks"]["items"][0]["id"]
          result = {{"songs": [song_id]}}
          ```
        
        Example 2:
        - User input: "Play my new playlist."
        - Output:
          ```python
          playlists = sp.current_user_playlists(limit=1)
          playlist_id = playlists["items"][0]["id"]
          result = {{"playlist": playlist_id}}
          ```
        
        Example 3:
        - User input: "Play a mix of Asake and Burna Boy."
        - Output:
          ```python
          results1 = sp.search(q="artist:Asake", type="track", limit=1)
          results2 = sp.search(q="artist:Burna Boy", type="track", limit=1)
          song_id1 = results1["tracks"]["items"][0]["id"]
          song_id2 = results2["tracks"]["items"][0]["id"]
          result = {{"songs": [song_id1, song_id2]}}
          ```
        
        IMPORTANT: Always assign the result to the variable `result`. Do not include any explanations or additional text.
        """
        
        # Get Gemini's response
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Log the raw response from Gemini
        logging.info(f"Raw response from Gemini: {response_text}")
        
        # Extract the code block from the response
        code_block = re.search(r'```python(.*?)```', response_text, re.DOTALL)
        if not code_block:
            logging.error("No code block found in Gemini's response")
            return {"error": "No code block found in Gemini's response"}
        
        code = code_block.group(1).strip()
        logging.info(f"Extracted code: {code}")
        
        # Execute the code and capture the result
        local_vars = {"sp": sp, "result": None}
        exec(code, {}, local_vars)
        
        # Get the result from the executed code
        result = local_vars.get("result", {})
        logging.info(f"Executed code result: {result}")
        
        return result
        
    except Exception as e:
        logging.error(f"Unexpected error in process_user_input: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

@app.route("/request-song", methods=["POST"])
def request_song():
    logging.info("Received request to /request-song endpoint")
    
    try:
        user_input = request.json.get("input")
        logging.info(f"Received user input: {user_input}")
        
        if not user_input:
            logging.error("No user input provided")
            return jsonify({"error": "User input is required!"}), 400

        # Process user input
        processed_input = process_user_input(user_input)
        logging.info(f"Processed input result: {processed_input}")
        
        if "error" in processed_input:
            logging.error(f"Error in processed input: {processed_input['error']}")
            return jsonify({"error": processed_input["error"]}), 500
            
        # Download songs or playlist
        if processed_input.get("songs"):
            song_ids = processed_input["songs"]
            for song_id in song_ids:
                if download_song(song_id):
                    logging.info(f"Successfully downloaded song: {song_id}")
                else:
                    logging.error(f"Failed to download song: {song_id}")
            return jsonify({"success": True, "songs": song_ids})
        
        elif processed_input.get("playlist"):
            playlist_id = processed_input["playlist"]
            # Implement playlist download logic here
            return jsonify({"success": True, "playlist": playlist_id})
        
        else:
            logging.error("No valid songs or playlist found in response")
            return jsonify({"error": "No valid songs or playlist found!"}), 400

    except Exception as e:
        logging.error(f"Unexpected error in request_song: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500
@app.route("/play/<song_id>", methods=["GET"])
def play_song(song_id):
    """Serve the downloaded song."""
    file_path = f"{song_id}.mp3"
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({"error": "Song not found!"}), 404

@app.route("/test-gemini", methods=["GET"])
def test_gemini():
    try:
        logging.info("Testing Gemini API connection...")
        logging.info(f"API Key present: {bool(GEMINI_API_KEY)}")
        
        response = model.generate_content("Just say 'test'")
        logging.info(f"Raw Gemini response: {response}")
        return jsonify({"success": True, "response": response.text})
    except Exception as e:
        logging.error(f"Gemini test failed: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/")
def index():
    """Serve the frontend."""
    return send_from_directory("static", "index.html")

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
