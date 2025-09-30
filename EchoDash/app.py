import os
import uuid
from flask import Flask, redirect, request, session, url_for
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Flask setup
app = Flask(__name__)
app.secret_key = "replace_this_with_a_secure_random_key"

# Spotify credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPE = "user-top-read"

# Helper function to create per-session SpotifyOAuth
def create_spotify_oauth(force_reauth=False):
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=f".cache-{session['uuid']}",
        show_dialog=force_reauth  # forces Spotify to show login screen
    )

# Home page
@app.route("/")
def home():
    return """
        <h1>Welcome to EchoDash</h1>
        <a href="/login">Log in with Spotify</a><br>
        <a href="/top-tracks">See Top Tracks</a><br>
        <a href="/top-artists">See Top Artists</a><br>
        <a href="/logout">Logout</a>
    """

# Login (always fresh login with show_dialog=True)
@app.route("/login")
def login():
    session["uuid"] = str(uuid.uuid4())  # new session ID = new cache
    cache_path = f".cache-{session['uuid']}"
    if os.path.exists(cache_path):
        os.remove(cache_path)

    sp_oauth = create_spotify_oauth(force_reauth=True)
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# Callback after Spotify login
@app.route("/callback")
def callback():
    sp_oauth = create_spotify_oauth()
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for("top_tracks"))

# Top Tracks page
@app.route("/top-tracks")
def top_tracks():
    sp_oauth = create_spotify_oauth()
    token_info = sp_oauth.get_cached_token()

    if not token_info:
        return redirect(url_for("login"))

    sp = spotipy.Spotify(auth=token_info["access_token"])
    results = sp.current_user_top_tracks(limit=50, time_range="long_term")

    tracks = [f"{t['name']} by {t['artists'][0]['name']}" for t in results["items"]]
    return "<h2>Your Top Tracks</h2><br>" + "<br>".join(tracks)

# Top Artists page
@app.route("/top-artists")
def top_artists():
    sp_oauth = create_spotify_oauth()
    token_info = sp_oauth.get_cached_token()

    if not token_info:
        return redirect(url_for("login"))

    sp = spotipy.Spotify(auth=token_info["access_token"])
    results = sp.current_user_top_artists(limit=10, time_range="long_term")

    artists = [
        f"{a['name']} ({a['genres'][0] if a['genres'] else 'No genre'})"
        for a in results["items"]
    ]
    return "<h2>Your Top Artists</h2><br>" + "<br>".join(artists)

# Logout route (clears session + token)
@app.route("/logout")
def logout():
    cache_path = f".cache-{session.get('uuid')}"
    if cache_path and os.path.exists(cache_path):
        os.remove(cache_path)
    session.clear()
    return redirect(url_for("home"))

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
