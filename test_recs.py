import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv

# Load secrets
load_dotenv()
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

scope = "user-read-email user-read-private user-top-read"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=scope
))

# Known good IDs
track_ids = ["32OlwWuMpZ6b0aN2RZOeMS"]   # Uptown Funk
artist_ids = ["3TVXtAsR1Inumwj472S9r4"]  # Drake
genres = ["pop"]

def try_recs(label, **kwargs):
    print(f"\n➡️ Trying {label} with params: {kwargs}")
    try:
        recs = sp.recommendations(limit=5, **kwargs)
        tracks = recs.get("tracks", [])
        if not tracks:
            print("⚠️ No tracks returned")
        else:
            for t in tracks:
                print(f"- {t['name']} by {', '.join(a['name'] for a in t['artists'])}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    # Test each seed type separately
    try_recs("Tracks only", seed_tracks=track_ids)
    try_recs("Artists only", seed_artists=artist_ids)
    try_recs("Genres only", seed_genres=genres)

    # Test combined seeds
    try_recs("Tracks + Artists", seed_tracks=track_ids, seed_artists=artist_ids)
    try_recs("Tracks + Genres", seed_tracks=track_ids, seed_genres=genres)
    try_recs("Artists + Genres", seed_artists=artist_ids, seed_genres=genres)

    # Full combo (tracks + artists + genres)
    try_recs("Tracks + Artists + Genres",
             seed_tracks=track_ids,
             seed_artists=artist_ids,
             seed_genres=genres)
