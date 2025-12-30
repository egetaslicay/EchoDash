import os
import uuid
from flask import Flask, redirect, request, session, url_for, render_template, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from recommender import get_recommendations
import plotly
import plotly.graph_objs as go
import json
import numpy as np
import database as db  


load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise ValueError("FLASK_SECRET_KEY must be set in .env file")

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPE = "user-top-read"


def create_spotify_oauth(force_reauth=False):
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=f".cache-{session.get('uuid','')}",
        show_dialog=force_reauth
    )


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

    # Get user profile and save to database
    try:
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user_profile = sp.current_user()

        user_id = db.get_or_create_user(
            spotify_id=user_profile["id"],
            display_name=user_profile.get("display_name"),
            email=user_profile.get("email"),
            profile_image=user_profile["images"][0]["url"] if user_profile.get("images") else None
        )
        session["user_id"] = user_id
    except Exception as e:
        print(f"Error saving user to database: {e}")

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

    # Get user profile
    user_profile = sp.current_user()
    user_image = user_profile["images"][0]["url"] if user_profile["images"] else None

    # Get filters
    time_range = request.args.get("time_range", "short_term")
    limit = int(request.args.get("limit", 10))

    # Get listening data
    tracks = sp.current_user_top_tracks(limit=limit, time_range=time_range)["items"]
    artists = sp.current_user_top_artists(limit=limit, time_range=time_range)["items"]

    # Save snapshot to database
    try:
        user_id = session.get("user_id")
        if user_id:
            # Simplified track/artist data for storage
            tracks_simple = [{
                'id': t['id'],
                'name': t['name'],
                'artist': t['artists'][0]['name'] if t.get('artists') else ''
            } for t in tracks]

            artists_simple = [{
                'id': a['id'],
                'name': a['name']
            } for a in artists]

            db.save_listening_snapshot(user_id, time_range, tracks_simple, artists_simple)
    except Exception as e:
        print(f"Error saving snapshot: {e}")

    # Get recommendations
    recs = get_recommendations(sp, tracks, artists, limit=10)

    # Save recommendations to database
    try:
        user_id = session.get("user_id")
        if user_id and recs:
            db.save_recommendations(user_id, recs)
    except Exception as e:
        print(f"Error saving recommendations: {e}")

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
