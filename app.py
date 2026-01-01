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

    # Get recommendations (with user feedback if available)
    user_id = session.get("user_id")
    recs = get_recommendations(sp, tracks, artists, limit=10, user_id=user_id)

    # Get user's liked and disliked tracks for display
    liked_tracks = []
    disliked_tracks = []
    if user_id:
        try:
            liked_tracks = db.get_liked_tracks(user_id)
            disliked_tracks = db.get_disliked_tracks(user_id)
        except Exception as e:
            print(f"Error fetching user feedback: {e}")

    # Save recommendations to database
    try:
        if user_id and recs:
            db.save_recommendations(user_id, recs)
    except Exception as e:
        print(f"Error saving recommendations: {e}")

    return render_template(
        "dashboard.html",
        tracks=tracks,
        artists=artists,
        recs=recs,
        liked_tracks=liked_tracks,
        disliked_tracks=disliked_tracks,
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

    user_id = session.get("user_id")
    recs = get_recommendations(sp, top_tracks, top_artists, limit=50, user_id=user_id)

    return render_template("recommendations.html", recs=recs)


@app.route("/analytics")
def analytics():
    """Analytics page - rebuilt from scratch."""
    token_info = session.get("token_info", None)
    if not token_info:
        return redirect(url_for("login"))

    sp = spotipy.Spotify(auth=token_info["access_token"])
    user_profile = sp.current_user()
    user_image = user_profile["images"][0]["url"] if user_profile["images"] else None

    # Get data
    try:
        artists = sp.current_user_top_artists(limit=20, time_range="short_term")["items"]
        tracks = sp.current_user_top_tracks(limit=20, time_range="short_term")["items"]
    except:
        artists, tracks = [], []

    charts_json = {}

    # Chart 1: Top Artists (horizontal bar)
    names = [a.get('name', 'Unknown')[:20] for a in artists[:10]]
    charts_json['top_artists_bar'] = json.dumps({
        'data': [{'type': 'bar', 'y': names[::-1], 'x': list(range(10, 0, -1)), 'orientation': 'h', 'marker': {'color': '#667eea'}}],
        'layout': {'title': 'Top 10 Artists', 'height': 400, 'margin': {'l': 150}}
    })

    # Chart 2: Genres (bar chart)
    genre_counts = {}
    for a in artists:
        for g in a.get('genres', []):
            genre_counts[g] = genre_counts.get(g, 0) + 1

    if genre_counts:
        top_g = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        charts_json['genre_distribution'] = json.dumps({
            'data': [{'type': 'bar', 'x': [g[0] for g in top_g], 'y': [g[1] for g in top_g], 'marker': {'color': '#764ba2'}}],
            'layout': {'title': 'Top Genres', 'height': 400, 'xaxis': {'tickangle': -45}}
        })
    else:
        charts_json['genre_distribution'] = json.dumps({
            'data': [],
            'layout': {'title': 'Top Genres', 'height': 400, 'annotations': [{'text': 'No genre data', 'showarrow': False, 'font': {'size': 16}}]}
        })

    # Chart 3: Artist Popularity (line)
    if artists:
        pop_vals = [a.get('popularity', 0) for a in artists[:15]]
        charts_json['artist_popularity'] = json.dumps({
            'data': [{'type': 'scatter', 'y': pop_vals, 'mode': 'markers+lines', 'marker': {'size': 10, 'color': '#4facfe'}, 'line': {'color': '#667eea'}}],
            'layout': {'title': 'Artist Popularity Trend', 'height': 400, 'yaxis': {'range': [0, 100]}}
        })
    else:
        charts_json['artist_popularity'] = json.dumps({'data': [], 'layout': {'title': 'Artist Popularity', 'height': 400}})

    # Chart 4: Track Popularity (bar)
    if tracks:
        t_names = [t.get('name', 'Unknown')[:20] for t in tracks[:10]]
        t_pop = [t.get('popularity', 0) for t in tracks[:10]]
        charts_json['track_popularity'] = json.dumps({
            'data': [{'type': 'bar', 'x': t_names, 'y': t_pop, 'marker': {'color': '#43e97b'}}],
            'layout': {'title': 'Top 10 Track Popularity', 'height': 400, 'xaxis': {'tickangle': -45}}
        })
    else:
        charts_json['track_popularity'] = json.dumps({'data': [], 'layout': {'title': 'Track Popularity', 'height': 400}})

    return render_template("analytics.html", charts=charts_json, user_image=user_image)


@app.route("/api/feedback", methods=["POST"])
def save_track_feedback():
    """API endpoint to save user feedback (like/dislike) for a track."""
    try:
        data = request.json
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        track_id = data.get("track_id")
        track_name = data.get("track_name")
        artist_name = data.get("artist_name")
        feedback = data.get("feedback")  # 1 for like, -1 for dislike

        if not all([track_id, track_name, artist_name, feedback is not None]):
            return jsonify({"error": "Missing required fields"}), 400

        if feedback not in [1, -1]:
            return jsonify({"error": "Feedback must be 1 (like) or -1 (dislike)"}), 400

        db.save_feedback(user_id, track_id, track_name, artist_name, feedback)

        return jsonify({
            "success": True,
            "message": "Feedback saved",
            "feedback": feedback
        })

    except Exception as e:
        print(f"Error saving feedback: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/feedback/<track_id>", methods=["DELETE"])
def delete_track_feedback(track_id):
    """API endpoint to delete feedback for a track."""
    try:
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        db.delete_feedback(user_id, track_id)

        return jsonify({
            "success": True,
            "message": "Feedback deleted"
        })

    except Exception as e:
        print(f"Error deleting feedback: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/feedback", methods=["GET"])
def get_all_feedback():
    """API endpoint to get all user feedback."""
    try:
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        feedback = db.get_user_feedback(user_id)

        return jsonify({
            "success": True,
            "feedback": feedback
        })

    except Exception as e:
        print(f"Error getting feedback: {e}")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True)
