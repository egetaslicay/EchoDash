# 🎧 EchoDash

**EchoDash** is a full-stack web application that connects to your favorite platforms (starting with Spotify) and visualizes your personal entertainment data through interactive dashboards.

## 🚀 Features

### 🎨 Modern, Clean UI
- **Glassmorphism design** with translucent cards and backdrop blur effects
- **Smooth animations** - entrance effects, hover states, and transitions
- **Gradient color scheme** - Purple-blue gradients with Spotify green accents
- **Responsive layout** - Optimized for desktop, tablet, and mobile
- **Interactive elements** - Hover effects, elevated cards, and smooth transitions
- **Professional typography** - Inter font for clean, modern readability

### 🎵 Smart Music Features
- 🎶 **Spotify integration** → Track your top tracks, artists, and listening history
- 🤖 **ML-powered recommendations** using audio features (acousticness, danceability, energy, tempo, etc.)
- 🎯 **Multi-tier recommendation system**:
  - Primary: ML-based cosine similarity on audio features
  - Fallback: Last.fm collaborative filtering
  - Basic: Spotify related artists
- 📊 **Visual similarity scores** - See how well each recommendation matches your taste
- 🎧 **Audio previews** - Listen to 30-second clips directly in the dashboard
- 🔗 **One-click Spotify links** - Open any track directly in Spotify

### 🛡️ Technical Features
- 🔑 Secure OAuth 2.0 authentication
- 🔐 Environment-based API key management
- ☁️ Cloud-ready deployment (Render/Heroku)
- 📱 Fully responsive design

## 🛠 Tech Stack

### Backend
- **Python (Flask)** - Web framework
- **Spotipy** - Spotify Web API client
- **RapidAPI Track Analysis** - Audio features (workaround for Spotify's deprecated endpoint)
- **scikit-learn** - ML algorithms (StandardScaler, cosine similarity)
- **Last.fm API** - Collaborative filtering fallback
- **NumPy & Pandas** - Data processing

### Frontend
- **HTML5 & CSS3** - Modern semantic markup and styling
- **Bootstrap 5.3** - Responsive grid system and utilities
- **Font Awesome 6.4** - Icon library
- **Google Fonts (Inter)** - Professional typography
- **Vanilla JavaScript** - Form handling and interactions
- **Jinja2** - Server-side templating

### Design
- **Glassmorphism** - Translucent UI elements with backdrop blur
- **Gradient color schemes** - Purple-blue gradients with Spotify green accents
- **Smooth animations** - CSS transitions and keyframe animations
- **Responsive design** - Mobile-first approach with breakpoints

### Deployment
- PostgreSQL (planned)
- Cloud-ready (Render/Heroku compatible)

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

## 🎨 UI Showcase

### Login Page
The login page features a **modern glassmorphism design** with:
- Translucent card with backdrop blur for a premium feel
- Animated floating particles in the background
- Clean feature list highlighting key capabilities
- ML-powered badge showcasing AI recommendations
- Spotify green CTA button with smooth hover effects
- Professional Inter font typography

### Dashboard
The dashboard offers a **clean, card-based layout** with:
- **Sticky navbar** with glassmorphism effect and profile image
- **Large, readable typography** - "Your Music Universe" header with gradient text
- **Filter controls** - Time range (last month/6 months/12 months) and limit selectors
- **Color-coded sections**:
  - 🟣 **Purple gradient** - Top Tracks section
  - 🌸 **Pink gradient** - Top Artists section
  - 🔵 **Cyan gradient** - ML-Powered Recommendations
- **Interactive track/artist cards**:
  - Album art thumbnails with rounded corners
  - Track/artist names with clear hierarchy
  - Hover effects that lift cards and add glow
- **Recommendation features**:
  - Visual similarity score badges (0-100%)
  - Built-in audio players for 30-second previews
  - "Open in Spotify" buttons for each track
- **Smooth animations** throughout (fade-in, slide-up, hover effects)

### Design System
- **Colors**: Purple-blue gradient background (#667eea → #764ba2)
- **Accents**: Spotify green (#1DB954), gradient badges
- **Typography**: Inter font family (300-800 weights)
- **Spacing**: Consistent 15-30px gaps and padding
- **Shadows**: Layered shadows for depth (10-50px blur)
- **Borders**: Rounded corners (15-30px radius)
- **Animations**: 0.3s ease transitions on all interactions

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
