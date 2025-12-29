# EchoDash

> A modern, ML-powered music analytics dashboard for Spotify with intelligent track recommendations based on audio feature analysis.

## Overview

EchoDash is a full-stack web application that visualizes your Spotify listening habits and provides personalized music recommendations using machine learning. Unlike simple collaborative filtering, EchoDash analyzes actual audio characteristics (acousticness, danceability, energy, tempo) to find tracks that genuinely match your musical taste.

## Tech Stack

**Backend**
- Flask - Python web framework
- Spotipy - Spotify Web API integration
- scikit-learn - ML algorithms (cosine similarity, StandardScaler)
- Pandas & NumPy - Data processing and analysis
- RapidAPI - Audio feature extraction
- Last.fm API - Collaborative filtering fallback

**Frontend**
- HTML5 & CSS3 - Modern semantic markup
- Bootstrap 5.3 - Responsive grid and components
- Font Awesome 6.4 - Icon library
- Google Fonts (Inter) - Typography
- Vanilla JavaScript - Client-side interactions

**Machine Learning**
- Audio feature extraction (8 dimensions)
- StandardScaler normalization
- Cosine similarity matching
- Multi-tier recommendation system

## Key Features

**Modern UI/UX**
- Glassmorphism design with backdrop blur effects
- Smooth animations and transitions
- Responsive layout for all devices
- Professional typography and spacing

**Smart Recommendations**
- ML-based audio feature analysis
- Real-time similarity scoring (0-100%)
- Multi-tier fallback system (ML → Last.fm → Basic)
- Audio preview integration
- Direct Spotify links

**Music Analytics**
- Top tracks by time period (1, 6, or 12 months)
- Top artists visualization
- Listening history analysis
- Customizable result limits (10-50 items)

## How It Works

### Recommendation Engine

**1. Data Collection**
- Authenticates via Spotify OAuth 2.0
- Fetches user's top tracks and artists
- Retrieves listening history across multiple time ranges

**2. Audio Feature Extraction**
- Queries RapidAPI for audio features of user's top tracks
- Builds candidate pool from top artists and related artists
- Fetches features for all candidate tracks

**3. ML Processing**
- Normalizes features using StandardScaler (mean=0, std=1)
- Calculates cosine similarity between user tracks and candidates
- Ranks candidates by similarity score

**4. Results**
- Enriches with Spotify metadata (album art, previews, links)
- Filters out already-known tracks
- Returns personalized recommendations

### Audio Features

The ML model analyzes 8 audio dimensions:

| Feature | Description | Range |
|---------|-------------|-------|
| Acousticness | Confidence measure if track is acoustic | 0.0 - 1.0 |
| Danceability | Suitability for dancing based on tempo/rhythm | 0.0 - 1.0 |
| Energy | Intensity and activity level | 0.0 - 1.0 |
| Instrumentalness | Predicts lack of vocals | 0.0 - 1.0 |
| Loudness | Overall loudness in decibels | -60 to 0 dB |
| Speechiness | Presence of spoken words | 0.0 - 1.0 |
| Tempo | Beats per minute | 0 - 250 BPM |
| Valence | Musical positivity/happiness | 0.0 - 1.0 |

### Fallback System

If RapidAPI is unavailable:
1. **Last.fm** - Collaborative filtering based on similar user behavior
2. **Basic** - Spotify's related artists algorithm

## Installation

### Prerequisites
- Python 3.8+
- Spotify Developer Account
- RapidAPI Account (free tier)

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/egetaslicay/EchoDash.git
cd EchoDash
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure API credentials**

Create a `.env` file:
```bash
cp .env.example .env
```

Add your credentials:
```env
# Spotify API
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:5000/callback

# Flask
FLASK_SECRET_KEY=your_secret_key

# RapidAPI (Required for ML recommendations)
RAPID_API_KEY=your_rapidapi_key

# Last.fm (Optional fallback)
LASTFM_API_KEY=your_lastfm_key
LASTFM_API_SECRET=your_lastfm_secret
```

4. **Run the application**
```bash
python app.py
```

5. **Access the dashboard**
```
http://localhost:5000
```

## API Setup

### Spotify API
1. Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create new application
3. Copy Client ID and Client Secret
4. Add `http://localhost:5000/callback` to Redirect URIs

### RapidAPI
1. Visit [RapidAPI Track Analysis](https://rapidapi.com/Glavier/api/track-analysis)
2. Subscribe to free tier
3. Copy your API key

**Why RapidAPI?** Spotify deprecated the audio features endpoint for new apps in late 2024. RapidAPI provides the same data through an alternative service.

### Last.fm (Optional)
1. Visit [Last.fm API](https://www.last.fm/api/account/create)
2. Create API account
3. Copy API Key and Shared Secret

## Project Structure

```
EchoDash/
├── app.py                      # Flask application & routes
├── recommender.py              # Multi-tier recommendation system
├── ml_recommender.py           # ML-based recommendation engine
├── audio_features_service.py   # RapidAPI integration
├── lastfm_service.py           # Last.fm API integration
├── templates/
│   ├── login.html              # Landing page
│   └── dashboard.html          # Main dashboard
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
└── README.md
```

## Architecture

```
User Request
    ↓
Flask Routes (app.py)
    ↓
Recommendation Engine (recommender.py)
    ↓
┌─────────────────────────────────────┐
│  1. ML Recommender (Primary)        │
│     - Audio feature analysis        │
│     - Cosine similarity matching    │
│     - RapidAPI integration          │
└─────────────────────────────────────┘
    ↓ (if fails)
┌─────────────────────────────────────┐
│  2. Last.fm (Fallback)              │
│     - Collaborative filtering       │
│     - Similar tracks/artists        │
└─────────────────────────────────────┘
    ↓ (if fails)
┌─────────────────────────────────────┐
│  3. Basic (Final Fallback)          │
│     - Spotify related artists       │
│     - Random similarity scores      │
└─────────────────────────────────────┘
```

## UI Design

### Login Page
- Glassmorphism card with backdrop blur
- Animated floating particles
- Feature highlights
- Spotify OAuth integration

### Dashboard
- Sticky navbar with user profile
- Time range filters (1M, 6M, 12M)
- Result limit controls (10-50)
- Color-coded sections:
  - Purple gradient: Top Tracks
  - Pink gradient: Top Artists
  - Cyan gradient: ML Recommendations
- Interactive cards with hover effects
- Audio preview players
- Direct Spotify links

### Design System
- **Colors**: Purple-blue gradient (#667eea → #764ba2)
- **Accents**: Spotify green (#1DB954)
- **Typography**: Inter (300-800 weight)
- **Spacing**: 15-30px consistent gaps
- **Shadows**: Layered elevation (10-50px blur)
- **Radius**: 15-30px rounded corners
- **Timing**: 0.3s ease transitions

## Performance

- Audio feature caching
- Rate limiting (5 req/sec)
- Batch API requests
- Lazy loading of album art
- Debounced filter changes

## Deployment

### Local Development
```bash
python app.py
```

### Production (Heroku)
```bash
heroku create your-app-name
git push heroku main
```

### Production (Render)
- Connect GitHub repository
- Set environment variables
- Deploy from dashboard

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- Spotify Web API for music data
- RapidAPI for audio feature workaround
- Last.fm for collaborative filtering
- scikit-learn for ML algorithms

## Contact

For questions or feedback, please open an issue on GitHub.

---

Built with passion for music and data science.
