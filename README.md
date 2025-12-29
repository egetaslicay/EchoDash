# 🎧 EchoDash

**EchoDash** is a full-stack web application that connects to your favorite platforms (starting with Spotify) and visualizes your personal entertainment data through interactive dashboards.

## 🚀 Features
- 🎶 Spotify integration → top tracks, artists, playlists
- 🎵 **Smart music recommendations** powered by Last.fm collaborative filtering
- 📊 Interactive charts powered by Plotly
- 🔑 Secure API key management with `.env`
- ☁️ Cloud-ready deployment (Render/Heroku)

## 🛠 Tech Stack
- Python (Flask)
- Spotipy (Spotify Web API)
- Last.fm API (Music recommendations)
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

#### Last.fm API Setup (for recommendations)
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
   LASTFM_API_KEY=your_lastfm_api_key
   LASTFM_API_SECRET=your_lastfm_api_secret
   ```

### 4. Run the application
```bash
python app.py
```

Visit `http://localhost:5000` in your browser and log in with Spotify!

## 🎯 How It Works

1. **Authentication**: OAuth 2.0 flow with Spotify
2. **Data Collection**: Fetches your top tracks, artists, and listening history
3. **Smart Recommendations**:
   - Uses Last.fm's collaborative filtering to find similar tracks and artists
   - Analyzes your top tracks to discover new music you'll love
   - Enriches recommendations with Spotify metadata (album art, previews)
4. **Visualization**: Interactive dashboards showing your music taste

## 📝 Note

If Last.fm API is not configured, the app will fall back to a basic recommendation algorithm. For best results, set up both Spotify and Last.fm APIs
