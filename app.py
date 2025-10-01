import os
import uuid
from flask import Flask, redirect, request, session, url_for, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from recommender import get_recommendations  # <-- use the one from recommender.py

# Load environment variables
load_dotenv()

# Flask setup
app = Flask(__name__)
app.secret_key = "replace_this_with_a_secure_random_key"

# Spotify credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPE = "user-top-read"

# Helper: per-session SpotifyOAuth
def create_spotify_oauth(force_reauth=False):
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=f".cache-{session.get('uuid','')}",
        show_dialog=force_reauth
    )

# Home (login page only)
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login")
def login():
    session["uuid"] = str(uuid.uuid4())
    cache_path = f".cache-{session['uuid']}"
    if os.path.exists(cache_path):
        os.remove(cache_path)

    sp_oauth = create_spotify_oauth(force_reauth=True)
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route("/callback")
def callback():
    sp_oauth = create_spotify_oauth()
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    cache_path = f".cache-{session.get('uuid')}"
    if cache_path and os.path.exists(cache_path):
        os.remove(cache_path)
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
def dashboard():
    token_info = session.get("token_info", None)
    if not token_info:
        return redirect(url_for("login"))

    sp = spotipy.Spotify(auth=token_info["access_token"])

    # User profile (for picture)
    user_profile = sp.current_user()
    user_image = user_profile["images"][0]["url"] if user_profile["images"] else None

    # Time range + limit
    time_range = request.args.get("time_range", "short_term")
    limit = int(request.args.get("limit", 10))

    tracks = sp.current_user_top_tracks(limit=limit, time_range=time_range)["items"]
    artists = sp.current_user_top_artists(limit=limit, time_range=time_range)["items"]

    # Recommendations (always based on medium_term for variety)
    recs = get_recommendations(sp, tracks, artists, limit=10)

    return render_template(
        "dashboard.html",
        tracks=tracks,
        artists=artists,
        recs=recs,
        time_range=time_range,
        limit=limit,
        user_image=user_image
    )

@app.route("/recommendations")
def recommendations():
    token_info = session.get("token_info", None)
    if not token_info:
        return redirect(url_for("login"))

    sp = spotipy.Spotify(auth=token_info["access_token"])

    top_tracks = sp.current_user_top_tracks(limit=50, time_range="medium_term")["items"]
    top_artists = sp.current_user_top_artists(limit=50, time_range="medium_term")["items"]

    recs = get_recommendations(sp, top_tracks, top_artists, limit=50)

    return render_template("recommendations.html", recs=recs)

if __name__ == "__main__":
    app.run(debug=True)
