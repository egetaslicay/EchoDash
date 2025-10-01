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
    scope=scope,
    open_browser=True,
    cache_path=".cache"
))

# Example IDs
track_id = "32OlwWuMpZ6b0aN2RZOeMS"   # Uptown Funk
artist_id = "3TVXtAsR1Inumwj472S9r4"  # Drake

print("\n--- TESTING ENDPOINTS ---")

# 1. Recommendations
try:
    recs = sp.recommendations(limit=5, seed_tracks=track_id)
    print("✅ Recommendations: WORKED, got", len(recs.get("tracks", [])), "tracks")
except Exception as e:
    print("❌ Recommendations FAILED:", e)

# 2. Audio Features
try:
    features = sp.audio_features([track_id])
    print("✅ Audio Features: WORKED →", features[0])
except Exception as e:
    print("❌ Audio Features FAILED:", e)

# 3. Audio Analysis
try:
    analysis = sp.audio_analysis(track_id)
    print("✅ Audio Analysis: WORKED → got sections:", len(analysis.get("sections", [])))
except Exception as e:
    print("❌ Audio Analysis FAILED:", e)

# 4. Related Artists
try:
    related = sp.artist_related_artists(artist_id)
    print("✅ Related Artists: WORKED → got", len(related.get("artists", [])), "artists")
except Exception as e:
    print("❌ Related Artists FAILED:", e)
