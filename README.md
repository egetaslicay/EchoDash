# 🎧 EchoDash

**EchoDash** is a full-stack web application that connects to your favorite platforms (starting with Spotify) and visualizes your personal entertainment data through interactive dashboards.

## 🚀 Features
- 🎶 Spotify integration → top tracks, artists, playlists
- 🎵 **ML-powered music recommendations** using audio features (acousticness, danceability, energy, tempo, etc.)
- 🤖 **Multi-tier recommendation system**:
  - Primary: ML-based cosine similarity on audio features
  - Fallback: Last.fm collaborative filtering
  - Basic: Spotify related artists
- 📊 Interactive charts powered by Plotly
- 🔑 Secure API key management with `.env`
- ☁️ Cloud-ready deployment (Render/Heroku)

## 🛠 Tech Stack
- Python (Flask)
- Spotipy (Spotify Web API)
- RapidAPI Track Analysis (Audio features - workaround for Spotify's deprecated endpoint)
- scikit-learn (ML algorithms - cosine similarity, KNN)
- Last.fm API (Collaborative filtering fallback)
- Plotly
- PostgreSQL (planned)

## ⚡ Setup

### 1. Clone the repository
```bash
git clone https://github.com/egetaslicay/EchoDash.git
cd EchoDash
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up API credentials

#### Spotify API Setup
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Copy your **Client ID** and **Client Secret**
4. Add `http://localhost:5000/callback` to the Redirect URIs

#### RapidAPI Setup (for audio features - REQUIRED for best recommendations)
1. Go to [RapidAPI Track Analysis](https://rapidapi.com/Glavier/api/track-analysis)
2. Sign up for a free account
3. Subscribe to the **free tier** of the Track Analysis API
4. Copy your **X-RapidAPI-Key** from the API dashboard

> **Why RapidAPI?** Spotify deprecated their audio features endpoint for new apps in late 2024. RapidAPI's Track Analysis provides the same data (acousticness, danceability, energy, etc.) that powers our ML recommendations.

#### Last.fm API Setup (optional - fallback recommendations)
1. Go to [Last.fm API Account Creation](https://www.last.fm/api/account/create)
2. Create a new API account
3. Copy your **API Key** and **Shared Secret**

#### Environment Configuration
1. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
2. Fill in your credentials in the `.env` file:
   ```env
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   SPOTIFY_REDIRECT_URI=http://localhost:5000/callback
   FLASK_SECRET_KEY=your_random_secret_key
   RAPID_API_KEY=your_rapidapi_key  # Required for ML recommendations
   LASTFM_API_KEY=your_lastfm_api_key  # Optional
   LASTFM_API_SECRET=your_lastfm_api_secret  # Optional
   ```

### 4. Run the application
```bash
python app.py
```

Visit `http://localhost:5000` in your browser and log in with Spotify!

## 🎯 How It Works

### ML-Based Recommendation Engine (Primary)

1. **Authentication**: OAuth 2.0 flow with Spotify
2. **Data Collection**: Fetches your top tracks, artists, and listening history
3. **Audio Feature Extraction**:
   - Fetches audio features for your top tracks (acousticness, danceability, energy, instrumentalness, loudness, tempo, speechiness, valence)
   - Builds candidate pool from top artists and related artists
   - Fetches audio features for all candidate tracks
4. **ML Processing**:
   - Normalizes features using StandardScaler (mean=0, std=1)
   - Calculates cosine similarity between candidate tracks and your top tracks
   - Ranks candidates by similarity score
5. **Enrichment**: Adds Spotify metadata (album art, preview URLs, artist info)
6. **Results**: Returns personalized recommendations based on actual musical characteristics

### Fallback System

If RapidAPI is not configured, the system falls back to:
1. **Last.fm Collaborative Filtering** - Recommendations based on what similar users listen to
2. **Basic Algorithm** - Uses Spotify's related artists API

### Audio Features Explained

- **Acousticness**: Confidence measure of whether the track is acoustic (0.0 to 1.0)
- **Danceability**: How suitable a track is for dancing based on tempo, rhythm, beat strength (0.0 to 1.0)
- **Energy**: Intensity and activity - energetic tracks feel fast, loud, and noisy (0.0 to 1.0)
- **Instrumentalness**: Predicts whether a track contains no vocals (0.0 to 1.0)
- **Loudness**: Overall loudness in decibels (dB)
- **Speechiness**: Detects presence of spoken words (0.0 to 1.0)
- **Tempo**: Overall estimated tempo in beats per minute (BPM)
- **Valence**: Musical positivity - high valence = happy/cheerful, low valence = sad/angry (0.0 to 1.0)

## 📝 Note

For **best recommendations**, set up RapidAPI. The ML algorithm provides superior recommendations compared to collaborative filtering alone because it analyzes actual musical characteristics.
