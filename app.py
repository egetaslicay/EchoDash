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
    tracks_short = sp.current_user_top_tracks(limit=20, time_range="short_term")["items"]
    artists_short = sp.current_user_top_artists(limit=10, time_range="short_term")["items"]

    # Get audio features for top tracks
    track_ids = [t['id'] for t in tracks_short]
    audio_features_raw = sp.audio_features(track_ids)
    audio_features = [f for f in audio_features_raw if f]  # Filter out None

    # Generate visualizations
    charts = {}

    # 1. Audio Features Radar Chart
    charts['audio_features_radar'] = create_audio_features_radar(audio_features)

    # 2. Top Artists Bar Chart
    charts['top_artists_bar'] = create_top_artists_chart(artists_short[:10])

    # 3. Mood/Energy Scatter Plot
    charts['mood_scatter'] = create_mood_scatter(tracks_short, audio_features)

    # 4. Audio Feature Distribution
    charts['feature_distribution'] = create_feature_distribution(audio_features)

    # Convert plots to JSON for embedding in HTML
    charts_json = {key: json.dumps(chart, cls=plotly.utils.PlotlyJSONEncoder)
                   for key, chart in charts.items()}

    return render_template(
        "analytics.html",
        charts=charts_json,
        user_image=user_image
    )


def create_audio_features_radar(audio_features):
    """Create radar chart of average audio features."""
    if not audio_features:
        return {}

    # Calculate average features
    features = ['danceability', 'energy', 'speechiness', 'acousticness', 'instrumentalness', 'valence']
    averages = {}

    for feature in features:
        values = [f.get(feature, 0) for f in audio_features if f.get(feature) is not None]
        averages[feature] = np.mean(values) if values else 0

    # Create radar chart
    fig = go.Figure(data=go.Scatterpolar(
        r=list(averages.values()),
        theta=[f.capitalize() for f in features],
        fill='toself',
        line=dict(color='#667eea', width=2),
        fillcolor='rgba(102, 126, 234, 0.3)'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1])
        ),
        showlegend=False,
        title="Your Music DNA",
        font=dict(family="Inter", size=14),
        height=400
    )

    return fig


def create_top_artists_chart(artists):
    """Create horizontal bar chart of top artists."""
    names = [a['name'] for a in artists]
    # Create ranking scores (10, 9, 8, ...)
    scores = list(range(len(names), 0, -1))

    fig = go.Figure(data=[
        go.Bar(
            y=names[::-1],  # Reverse to show #1 at top
            x=scores[::-1],
            orientation='h',
            marker=dict(
                color=scores[::-1],
                colorscale=[[0, '#764ba2'], [1, '#667eea']],
                showscale=False
            )
        )
    ])

    fig.update_layout(
        title="Top 10 Artists",
        xaxis_title="Ranking Score",
        yaxis_title="",
        font=dict(family="Inter", size=12),
        height=500,
        showlegend=False
    )

    return fig


def create_mood_scatter(tracks, audio_features):
    """Create scatter plot of energy vs valence (mood quadrants)."""
    if not audio_features:
        return {}

    energy = [f.get('energy', 0) for f in audio_features]
    valence = [f.get('valence', 0) for f in audio_features]
    track_names = [t['name'][:30] + '...' if len(t['name']) > 30 else t['name']
                   for t in tracks[:len(audio_features)]]

    fig = go.Figure(data=go.Scatter(
        x=valence,
        y=energy,
        mode='markers',
        marker=dict(
            size=12,
            color=energy,
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Energy")
        ),
        text=track_names,
        hovertemplate='<b>%{text}</b><br>Valence: %{x:.2f}<br>Energy: %{y:.2f}<extra></extra>'
    ))

    # Add quadrant lines
    fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=0.5, line_dash="dash", line_color="gray", opacity=0.5)

    # Add quadrant labels
    fig.add_annotation(x=0.75, y=0.75, text="Energetic<br>& Happy", showarrow=False, opacity=0.5)
    fig.add_annotation(x=0.25, y=0.75, text="Energetic<br>& Dark", showarrow=False, opacity=0.5)
    fig.add_annotation(x=0.75, y=0.25, text="Calm<br>& Happy", showarrow=False, opacity=0.5)
    fig.add_annotation(x=0.25, y=0.25, text="Calm<br>& Dark", showarrow=False, opacity=0.5)

    fig.update_layout(
        title="Mood Map (Energy vs Positivity)",
        xaxis_title="Valence (Musical Positivity)",
        yaxis_title="Energy",
        font=dict(family="Inter", size=12),
        height=500
    )

    return fig


def create_feature_distribution(audio_features):
    """Create histogram of tempo distribution."""
    if not audio_features:
        return {}

    tempos = [f.get('tempo', 0) for f in audio_features if f.get('tempo')]

    fig = go.Figure(data=[
        go.Histogram(
            x=tempos,
            nbinsx=20,
            marker=dict(
                color='#667eea',
                line=dict(color='white', width=1)
            )
        )
    ])

    fig.update_layout(
        title="Tempo Distribution (BPM)",
        xaxis_title="Tempo (BPM)",
        yaxis_title="Number of Tracks",
        font=dict(family="Inter", size=12),
        height=350
    )

    return fig


if __name__ == "__main__":
    app.run(debug=True)
