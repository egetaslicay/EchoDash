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
    """Analytics page with Plotly visualizations."""
    token_info = session.get("token_info", None)
    if not token_info:
        return redirect(url_for("login"))

    sp = spotipy.Spotify(auth=token_info["access_token"])

    # Get user profile
    user_profile = sp.current_user()
    user_image = user_profile["images"][0]["url"] if user_profile["images"] else None

    # Get listening data
    try:
        tracks_short = sp.current_user_top_tracks(limit=20, time_range="short_term")["items"]
        artists_short = sp.current_user_top_artists(limit=20, time_range="short_term")["items"]
    except Exception as e:
        print(f"Error fetching Spotify data: {e}")
        tracks_short = []
        artists_short = []

    # Generate visualizations (without deprecated audio features API)
    charts = {}

    try:
        # 1. Top Artists Bar Chart
        if artists_short:
            charts['top_artists_bar'] = create_top_artists_chart(artists_short[:10])
    except Exception as e:
        print(f"Error creating top artists chart: {e}")

    try:
        # 2. Genre Distribution Pie Chart
        if artists_short:
            charts['genre_distribution'] = create_genre_distribution(artists_short)
    except Exception as e:
        print(f"Error creating genre distribution chart: {e}")

    try:
        # 3. Artist Popularity Chart
        if artists_short:
            charts['artist_popularity'] = create_artist_popularity_chart(artists_short[:15])
    except Exception as e:
        print(f"Error creating artist popularity chart: {e}")

    try:
        # 4. Track Popularity Chart
        if tracks_short:
            charts['track_popularity'] = create_track_popularity_chart(tracks_short)
    except Exception as e:
        print(f"Error creating track popularity chart: {e}")

    # Convert plots to JSON for embedding in HTML
    charts_json = {}
    for key, chart in charts.items():
        try:
            charts_json[key] = json.dumps(chart, cls=plotly.utils.PlotlyJSONEncoder)
        except Exception as e:
            print(f"Error encoding chart {key}: {e}")
            charts_json[key] = '{}'

    return render_template(
        "analytics.html",
        charts=charts_json,
        user_image=user_image
    )


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


def create_top_artists_chart(artists):
    """Create horizontal bar chart of top artists."""
    if not artists or len(artists) == 0:
        # Return empty figure with message
        fig = go.Figure()
        fig.update_layout(
            title="Top Artists",
            height=400,
            annotations=[dict(text="No data available", showarrow=False, font=dict(size=16, color="gray"))]
        )
        return fig

    # Limit to top 10
    artists = artists[:10]
    names = [a.get('name', 'Unknown') for a in artists]
    scores = list(range(len(names), 0, -1))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=names[::-1],
        x=scores[::-1],
        orientation='h',
        marker_color='#667eea'
    ))

    fig.update_layout(
        title="Top 10 Artists",
        height=400,
        showlegend=False,
        margin=dict(l=150, r=20, t=40, b=40)
    )

    return fig


def create_genre_distribution(artists):
    """Create bar chart of genre distribution."""
    if not artists:
        fig = go.Figure()
        fig.update_layout(
            title="Top Genres",
            height=400,
            annotations=[dict(text="No data available", showarrow=False, font=dict(size=16, color="gray"))]
        )
        return fig

    # Extract genres
    genre_counts = {}
    for artist in artists:
        for genre in artist.get('genres', []):
            genre_counts[genre] = genre_counts.get(genre, 0) + 1

    if not genre_counts:
        fig = go.Figure()
        fig.update_layout(
            title="Top Genres",
            height=400,
            annotations=[dict(text="No genre data available", showarrow=False, font=dict(size=16, color="gray"))]
        )
        return fig

    # Top 8 genres
    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    genres = [g[0] for g in sorted_genres]
    counts = [g[1] for g in sorted_genres]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=genres,
        y=counts,
        marker_color='#764ba2'
    ))

    fig.update_layout(
        title="Top Genres in Your Music",
        height=400,
        showlegend=False,
        xaxis_tickangle=-45
    )

    return fig


def create_artist_popularity_chart(artists):
    """Create simple scatter plot of artist popularity."""
    if not artists:
        fig = go.Figure()
        fig.update_layout(
            title="Artist Popularity",
            height=400,
            annotations=[dict(text="No data available", showarrow=False, font=dict(size=16, color="gray"))]
        )
        return fig

    names = [a.get('name', 'Unknown')[:15] for a in artists]
    popularity = [a.get('popularity', 0) for a in artists]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(1, len(names) + 1)),
        y=popularity,
        mode='markers+lines',
        marker=dict(size=10, color='#4facfe'),
        line=dict(color='#667eea', width=2),
        text=names,
        hovertemplate='%{text}<br>Popularity: %{y}<extra></extra>'
    ))

    fig.update_layout(
        title="Artist Popularity Trend",
        xaxis_title="Rank",
        yaxis_title="Popularity (0-100)",
        height=400,
        showlegend=False
    )

    return fig


def create_track_popularity_chart(tracks):
    """Create simple bar chart of track popularity."""
    if not tracks:
        fig = go.Figure()
        fig.update_layout(
            title="Track Popularity",
            height=400,
            annotations=[dict(text="No data available", showarrow=False, font=dict(size=16, color="gray"))]
        )
        return fig

    # Limit to top 10 for readability
    tracks = tracks[:10]
    names = [t.get('name', 'Unknown')[:20] for t in tracks]
    popularity = [t.get('popularity', 0) for t in tracks]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names,
        y=popularity,
        marker_color='#43e97b'
    ))

    fig.update_layout(
        title="Top 10 Track Popularity",
        height=400,
        showlegend=False,
        xaxis_tickangle=-45,
        yaxis_range=[0, 100]
    )

    return fig


if __name__ == "__main__":
    app.run(debug=True)
