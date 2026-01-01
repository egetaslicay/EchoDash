"""
ML-based Music Recommendation Engine
Uses Spotify's recommendations API with randomized seeds and audio features.
Incorporates user feedback (likes/dislikes) for personalization.
"""

import numpy as np
import pandas as pd
from typing import List, Dict
import random
import database as db


def get_recommendations_ml(sp, top_tracks, top_artists, limit=50, user_id=None):
    """
    Generate music recommendations using Spotify's recommendations API.

    Algorithm:
    1. Build diverse seed pool from user's top tracks and artists
    2. Analyze user's audio feature preferences from listening history
    3. Make multiple calls to sp.recommendations() with:
       - Randomized seed combinations (max 5 seeds per call)
       - Tunable audio features based on user preferences
       - Varying parameters for diversity
    4. Filter out duplicates, liked/disliked tracks
    5. Score and rank results

    Args:
        sp: Spotipy client
        top_tracks: User's top tracks
        top_artists: User's top artists
        limit: Number of recommendations to return
        user_id: User ID for feedback and history

    Returns:
        List of recommended tracks with metadata
    """

    print("=== Spotify Recommendations API Engine ===")

    # 0. Get user feedback and recommendation history
    user_feedback = {}
    liked_tracks = []
    liked_track_ids = set()
    disliked_track_ids = set()
    recently_recommended_ids = set()

    if user_id:
        print("Step 0: Loading user feedback and history...")
        user_feedback = db.get_user_feedback(user_id)
        liked_tracks = db.get_liked_tracks(user_id)
        liked_track_ids = {t['track_id'] for t in liked_tracks}
        disliked_track_ids = {t['track_id'] for t in db.get_disliked_tracks(user_id)}
        recently_recommended_ids = db.get_recently_recommended_track_ids(user_id, days=3)
        print(f"  Found {len(liked_tracks)} liked tracks and {len(disliked_track_ids)} disliked tracks")
        print(f"  Found {len(recently_recommended_ids)} recently recommended tracks (last 3 days)")
        print(f"  Excluding {len(liked_track_ids) + len(disliked_track_ids) + len(recently_recommended_ids)} tracks from recommendations")

    # 1. Build seed pools
    print("\nStep 1: Building seed pools...")

    # Get track IDs and artist IDs from user's top items
    seed_track_ids = [t["id"] for t in top_tracks[:50] if "id" in t]
    seed_artist_ids = [a["id"] for a in top_artists[:50] if "id" in a]

    # Get user's genre preferences
    user_genres = []
    for artist in top_artists[:20]:
        user_genres.extend(artist.get("genres", []))
    user_genres = list(set(user_genres))  # Remove duplicates

    # Get available seed genres from Spotify
    try:
        available_genres = sp.recommendation_genre_seeds()["genres"]
        # Filter to only use genres that Spotify accepts as seeds
        seed_genres = [g for g in user_genres if g in available_genres]
    except Exception as e:
        print(f"  Warning: Could not fetch available genres: {e}")
        seed_genres = []

    print(f"  Seed pools: {len(seed_track_ids)} tracks, {len(seed_artist_ids)} artists, {len(seed_genres)} genres")

    # 2. Analyze user's audio feature preferences
    print("\nStep 2: Analyzing user's audio feature preferences...")
    audio_features = analyze_user_audio_preferences(sp, seed_track_ids[:50])

    if audio_features:
        print(f"  Target features: energy={audio_features.get('target_energy', 0.5):.2f}, "
              f"danceability={audio_features.get('target_danceability', 0.5):.2f}, "
              f"valence={audio_features.get('target_valence', 0.5):.2f}")
    else:
        print("  Using default audio features")
        audio_features = {}

    # 3. Generate multiple batches of recommendations with different seeds
    print("\nStep 3: Generating recommendations with randomized seeds...")
    all_recommendations = []
    seen_track_ids = set()
    filtered_count = 0

    # Calculate how many batches we need (accounting for duplicates/filtering)
    # We'll generate more than needed and filter down
    batches_needed = max(5, (limit // 10) + 2)

    for batch in range(batches_needed):
        try:
            # Randomize seed selection for each batch
            batch_seeds = select_random_seeds(
                seed_track_ids,
                seed_artist_ids,
                seed_genres,
                batch_num=batch
            )

            # Add some randomization to audio features for diversity
            batch_audio_features = randomize_audio_features(audio_features, variation=0.15)

            print(f"\n  Batch {batch + 1}/{batches_needed}:")
            print(f"    Seeds: artists={len(batch_seeds.get('seed_artists', []))}, "
                  f"tracks={len(batch_seeds.get('seed_tracks', []))}, "
                  f"genres={len(batch_seeds.get('seed_genres', []))}")
            print(f"    Audio features: {list(batch_audio_features.keys())}")

            # Call Spotify's recommendations API
            print(f"    Calling sp.recommendations()...")
            recommendations_response = sp.recommendations(
                limit=20,  # Get 20 per batch
                **batch_seeds,
                **batch_audio_features,
                market='US'
            )

            tracks = recommendations_response.get('tracks', [])
            print(f"    ✓ Retrieved {len(tracks)} recommendations from Spotify")

            # Process each track
            for track in tracks:
                track_id = track['id']

                # Skip duplicates
                if track_id in seen_track_ids:
                    continue

                # Filter out liked, disliked, and recently recommended
                if (track_id in liked_track_ids or
                    track_id in disliked_track_ids or
                    track_id in recently_recommended_ids):
                    filtered_count += 1
                    continue

                # Add to recommendations
                seen_track_ids.add(track_id)
                all_recommendations.append({
                    'id': track_id,
                    'name': track['name'],
                    'artist': ', '.join([a['name'] for a in track['artists']]),
                    'artist_id': track['artists'][0]['id'] if track['artists'] else None,
                    'popularity': track.get('popularity', 50),
                    'album_image': track['album']['images'][0]['url'] if track.get('album', {}).get('images') else None,
                    'preview_url': track.get('preview_url'),
                    'batch': batch
                })

            # Stop if we have enough recommendations
            if len(all_recommendations) >= limit * 1.5:
                break

        except Exception as e:
            print(f"  ❌ ERROR in batch {batch + 1}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n  Total collected: {len(all_recommendations)} unique tracks")
    if filtered_count > 0:
        print(f"  ⛔ Filtered out {filtered_count} tracks (liked + disliked + recently recommended)")

    if not all_recommendations:
        print("No recommendations found")
        return []

    # 4. Score and rank recommendations
    print("\nStep 4: Scoring and ranking recommendations...")

    # Get liked artists for boosting
    liked_artists = set()
    if liked_tracks:
        for liked in liked_tracks:
            artist = liked.get('artist_name', '')
            if artist:
                liked_artists.add(artist)

    # Calculate scores
    for rec in all_recommendations:
        score = 0.0

        # Popularity score (30% weight)
        popularity_score = rec['popularity'] / 100.0
        score += popularity_score * 0.3

        # Boost if artist matches liked tracks (25% bonus)
        if liked_artists and rec['artist'] in liked_artists:
            score += 0.25

        # Newer batches get slight penalty to prefer earlier (more relevant) results
        batch_penalty = rec['batch'] * 0.02
        score -= batch_penalty

        # Add randomization for diversity (±10%)
        random_factor = random.uniform(-0.1, 0.1)
        score += random_factor

        rec['score'] = score

    # Sort by score
    all_recommendations.sort(key=lambda x: x['score'], reverse=True)

    # 5. Apply diversity filter
    print("\nStep 5: Applying diversity filters...")
    final_recommendations = []
    artist_counts = {}
    max_per_artist = 2

    for rec in all_recommendations:
        artist_id = rec['artist_id']

        # Limit tracks per artist for diversity
        if artist_id and artist_counts.get(artist_id, 0) >= max_per_artist:
            continue

        final_recommendations.append({
            'id': rec['id'],
            'name': rec['name'],
            'artist': rec['artist'],
            'album_image': rec['album_image'],
            'preview_url': rec['preview_url'],
            'score': round(rec['score'], 3),
            'source': 'Spotify Recommendations API'
        })

        if artist_id:
            artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1

        if len(final_recommendations) >= limit:
            break

    print(f"\n✓ Generated {len(final_recommendations)} diverse recommendations")
    return final_recommendations


def select_random_seeds(track_ids, artist_ids, genre_ids, batch_num=0):
    """
    Select a random combination of seeds (max 5 total).
    Uses batch number as random seed for reproducibility within a session.

    Spotify API allows up to 5 seeds total across tracks, artists, and genres.
    """
    random.seed(batch_num + random.randint(0, 10000))

    seeds = {}
    total_seeds = 0
    max_seeds = 5

    # Randomly decide seed distribution
    # We want variety across batches
    strategies = [
        # More tracks
        {'tracks': 3, 'artists': 2, 'genres': 0},
        {'tracks': 3, 'artists': 1, 'genres': 1},
        # More artists
        {'tracks': 2, 'artists': 3, 'genres': 0},
        {'tracks': 1, 'artists': 3, 'genres': 1},
        # Balanced
        {'tracks': 2, 'artists': 2, 'genres': 1},
        {'tracks': 1, 'artists': 2, 'genres': 2},
        # Genre-heavy
        {'tracks': 1, 'artists': 1, 'genres': 3},
        {'tracks': 2, 'artists': 0, 'genres': 3},
    ]

    # Pick a strategy based on batch number
    strategy = strategies[batch_num % len(strategies)]

    # Select random seeds according to strategy
    if track_ids and strategy['tracks'] > 0:
        selected = random.sample(track_ids, min(strategy['tracks'], len(track_ids)))
        seeds['seed_tracks'] = selected

    if artist_ids and strategy['artists'] > 0:
        selected = random.sample(artist_ids, min(strategy['artists'], len(artist_ids)))
        seeds['seed_artists'] = selected

    if genre_ids and strategy['genres'] > 0:
        selected = random.sample(genre_ids, min(strategy['genres'], len(genre_ids)))
        seeds['seed_genres'] = selected

    return seeds


def analyze_user_audio_preferences(sp, track_ids):
    """
    Analyze user's audio feature preferences from their top tracks.
    Returns target audio features for recommendations API.
    """
    if not track_ids:
        return {}

    try:
        # Get audio features for user's tracks (in batches of 100)
        all_features = []
        for i in range(0, min(len(track_ids), 50), 50):
            batch = track_ids[i:i+50]
            features = sp.audio_features(batch)
            all_features.extend([f for f in features if f is not None])

        if not all_features:
            return {}

        # Calculate average values
        avg_features = {
            'energy': np.mean([f['energy'] for f in all_features]),
            'danceability': np.mean([f['danceability'] for f in all_features]),
            'valence': np.mean([f['valence'] for f in all_features]),
            'acousticness': np.mean([f['acousticness'] for f in all_features]),
            'instrumentalness': np.mean([f['instrumentalness'] for f in all_features]),
        }

        # Return as target_ parameters for recommendations API
        return {
            'target_energy': round(avg_features['energy'], 2),
            'target_danceability': round(avg_features['danceability'], 2),
            'target_valence': round(avg_features['valence'], 2),
            'target_acousticness': round(avg_features['acousticness'], 2),
            'target_instrumentalness': round(avg_features['instrumentalness'], 2),
        }

    except Exception as e:
        print(f"  Warning: Could not analyze audio features: {e}")
        return {}


def randomize_audio_features(base_features, variation=0.15):
    """
    Add random variation to audio features for diversity.
    Variation determines how much to vary (0.15 = ±15%)
    """
    if not base_features:
        return {}

    randomized = {}
    for key, value in base_features.items():
        # Add random variation
        varied_value = value + random.uniform(-variation, variation)
        # Clamp to valid range [0, 1]
        randomized[key] = max(0.0, min(1.0, varied_value))

    return randomized
