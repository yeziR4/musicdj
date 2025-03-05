from flask import Flask, jsonify, request, redirect, url_for, send_from_directory
import requests
import os
import json
import google.generativeai as genai
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
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

# Initialize Spotify client with client credentials flow
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    ))
    logging.info("Successfully initialized Spotify client with client credentials")
except Exception as e:
    logging.error(f"Failed to initialize Spotify client: {str(e)}")

def generate_dj_adlib(song_name, artist_name):
    """Generate DJ adlib using Gemini."""
    prompt = f"Generate a short and energetic DJ adlib for the song '{song_name}' by {artist_name}."
    response = model.generate_content(prompt)
    return response.text

# Flask Routes

@app.route("/auth/login", methods=["GET"])
def auth_login():
    """Redirect user to Spotify login page."""
    # Updated scopes to include streaming capabilities
    SCOPES = "playlist-read-private user-library-read streaming user-read-email user-read-private"
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
    
    # Return tokens to the client for Web Playback SDK usage
    return redirect(
        url_for(
            "index",
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data["expires_in"],
        )
    )

import re
def process_user_input(user_input):
    try:
        logging.info("Processing user input: {}".format(user_input))
        
        # Extract artist name (handling more complex input)
        input_parts = user_input.split()
        artist_name = input_parts[1] if len(input_parts) > 1 else ""
        
        # Simplified prompt 
        prompt = """
        You are a music assistant integrated with the Spotify API. 
        The user request is: '{0}'
        
        Identify the artist: '{1}'
        
        Task:
        1. Find the newest song for this artist
        2. Generate Python code to query the Spotify API
        3. Return code in this format:
           ```python
           # Query Spotify API for most recent track
           results = sp.search(q="artist:{1}", type="track", limit=10)
           
           # Sort tracks by release date
           sorted_tracks = sorted(
               results["tracks"]["items"], 
               key=lambda x: x.get('album', {}).get('release_date', ''), 
               reverse=True
           )
           
           # Process results
           if not sorted_tracks:
               result = {"error": "No tracks found"}
           else:
               newest_track = sorted_tracks[0]
               song_id = newest_track["id"]
               song_name = newest_track["name"]
               artist_name = newest_track["artists"][0]["name"]
               result = {"songs": [{
                   "id": song_id,
                   "name": song_name,
                   "artist": artist_name,
                   "uri": "spotify:track:" + song_id
               }]}
           ```
        
        Instructions:
        - Sort tracks by release date
        - Return most recent track
        - Ensure robust error handling
        """.format(user_input, artist_name)
        
        # Get Gemini's response
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Log the raw response from Gemini
        logging.info("Raw response from Gemini: {}".format(response_text))
        
        # Extract the code block from the response
        code_block = re.search(r'```python(.*?)```', response_text, re.DOTALL)
        if not code_block:
            logging.error("No code block found in Gemini's response")
            return {"error": "No code block found in Gemini's response"}
        
        code = code_block.group(1).strip()
        
        # Remove the `sort` parameter if it exists
        code = re.sub(r',\s*sort="[^"]*"', '', code)
        logging.info("Extracted code (after removing sort): {}".format(code))
        
        # Execute the code and capture the result
        local_vars = {"sp": sp, "result": None}
        try:
            exec(code, {}, local_vars)
            
            # Get the result from the executed code
            result = local_vars.get("result", {})
            logging.info("Executed code result: {}".format(result))
            
            return result
        except Exception as exec_error:
            logging.error("Error executing Gemini-generated code: {}".format(str(exec_error)))
            return {"error": "Error in search query: {}".format(str(exec_error))}
        
    except Exception as e:
        # Explicitly convert to string to avoid formatting issues
        error_message = str(e)
        logging.error("Unexpected error in process_user_input: {}".format(error_message))
        return {"error": "Unexpected error: {}".format(error_message)}

            
      
        
      
      

         


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
            
        # Return track info for Web Playback SDK
        if processed_input.get("songs"):
            songs = processed_input["songs"]
            first_song = songs[0]
            
            # Generate adlib for the song
            adlib = generate_dj_adlib(first_song["name"], first_song["artist"])
            
            return jsonify({
                "type": "track",
                "tracks": songs,
                "adlib": adlib
            })
        
        elif processed_input.get("playlist"):
            playlist = processed_input["playlist"]
            return jsonify({
                "type": "playlist",
                "playlist": playlist
            })
        
        else:
            logging.error("No valid songs or playlist found in response")
            return jsonify({"error": "No valid songs or playlist found!"}), 400

    except Exception as e:
        logging.error(f"Unexpected error in request_song: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route("/refresh-token", methods=["POST"])
def refresh_token():
    """Refresh the Spotify access token."""
    refresh_token = request.json.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "Refresh token is required!"}), 400

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        },
    )

    if response.status_code != 200:
        return jsonify({"error": "Failed to refresh token!"}), 400

    return jsonify(response.json())

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
