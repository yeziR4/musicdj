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
           # Check if results are empty
           if not results["tracks"]["items"]:
               result = {"error": "No matching tracks found"}
           else:
               song_id = results["tracks"]["items"][0]["id"]
               song_name = results["tracks"]["items"][0]["name"]
               artist_name = results["tracks"]["items"][0]["artists"][0]["name"]
               result = {{"songs": [{{
                   "id": song_id,
                   "name": song_name,
                   "artist": artist_name,
                   "uri": f"spotify:track:{{song_id}}"
               }}]}}
           ```
        
        Example 1:
        - User input: "Play Asake's latest song."
        - Output:
          ```python
          results = sp.search(q="artist:Asake", type="track", limit=1)
          if not results["tracks"]["items"]:
              result = {"error": "No matching tracks found"}
          else:
              song_id = results["tracks"]["items"][0]["id"]
              song_name = results["tracks"]["items"][0]["name"]
              artist_name = results["tracks"]["items"][0]["artists"][0]["name"]
              result = {{"songs": [{{
                  "id": song_id,
                  "name": song_name,
                  "artist": artist_name,
                  "uri": f"spotify:track:{{song_id}}"
              }}]}}
          ```
        
        Example 2:
        - User input: "Play my new playlist."
        - Output:
          ```python
          playlists = sp.current_user_playlists(limit=1)
          if not playlists["items"]:
              result = {"error": "No playlists found"}
          else:
              playlist_id = playlists["items"][0]["id"]
              playlist_name = playlists["items"][0]["name"]
              result = {{"playlist": {{
                  "id": playlist_id,
                  "name": playlist_name,
                  "uri": f"spotify:playlist:{{playlist_id}}"
              }}}}
          ```
        
        Example 3:
        - User input: "Play a mix of Asake and Burna Boy."
        - Output:
          ```python
          results1 = sp.search(q="artist:Asake", type="track", limit=1)
          results2 = sp.search(q="artist:Burna Boy", type="track", limit=1)
          
          if not results1["tracks"]["items"] or not results2["tracks"]["items"]:
              result = {"error": "Could not find tracks for one or both artists"}
          else:
              song_id1 = results1["tracks"]["items"][0]["id"]
              song_name1 = results1["tracks"]["items"][0]["name"]
              artist_name1 = results1["tracks"]["items"][0]["artists"][0]["name"]
              song_id2 = results2["tracks"]["items"][0]["id"] 
              song_name2 = results2["tracks"]["items"][0]["name"]
              artist_name2 = results2["tracks"]["items"][0]["artists"][0]["name"]
              result = {{"songs": [
                  {{
                      "id": song_id1,
                      "name": song_name1,
                      "artist": artist_name1,
                      "uri": f"spotify:track:{{song_id1}}"
                  }},
                  {{
                      "id": song_id2,
                      "name": song_name2,
                      "artist": artist_name2,
                      "uri": f"spotify:track:{{song_id2}}"
                  }}
              ]}}
          ```
        
        IMPORTANT: 
        - Always check if search results are empty before accessing items
        - Do not include the `sort` parameter in the `sp.search()` method.
        - Always assign the result to the variable `result`. 
        - Include URIs and human-readable names for playback.
        - Do not include any explanations or additional text.
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
        
        # Remove the `sort` parameter if it exists
        code = re.sub(r',\s*sort="[^"]*"', '', code)
        logging.info(f"Extracted code (after removing sort): {code}")
        
        # Execute the code and capture the result
        local_vars = {"sp": sp, "result": None}
        try:
            exec(code, {}, local_vars)
            
            # Get the result from the executed code
            result = local_vars.get("result", {})
            logging.info(f"Executed code result: {result}")
            
            return result
        except Exception as exec_error:
            logging.error(f"Error executing Gemini-generated code: {str(exec_error)}")
            return {"error": f"Error in search query: {str(exec_error)}"}
        
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
            error_message = processed_input["error"]
            logging.error(f"Error in processed input: {error_message}")
            
            # Provide a user-friendly message
            if "No matching tracks found" in error_message or "Could not find tracks" in error_message:
                return jsonify({
                    "error": "I couldn't find that song or artist on Spotify. Please try a different search."
                }), 404
            elif "list index out of range" in error_message:
                return jsonify({
                    "error": "No results found for your query. Please try a more specific request."
                }), 404
            else:
                return jsonify({"error": error_message}), 500
            
        # Return track info for Web Playback SDK
        if processed_input.get("songs"):
            songs = processed_input["songs"]
            first_song = songs[0]
            
            # Generate adlib for the song
            try:
                adlib = generate_dj_adlib(first_song["name"], first_song["artist"])
            except Exception as e:
                logging.error(f"Failed to generate adlib: {str(e)}")
                adlib = f"Now playing {first_song['name']} by {first_song['artist']}!"
            
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
            return jsonify({
                "error": "I couldn't process that request. Please try asking in a different way."
            }), 400

    except Exception as e:
        logging.error(f"Unexpected error in request_song: {str(e)}")
        return jsonify({
            "error": "Something went wrong. Please try again."
        }), 500
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
