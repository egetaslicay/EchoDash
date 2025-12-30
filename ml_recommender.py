"""
ML-based Music Recommendation Engine
Uses Spotify's native audio features API with weighted cosine similarity.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict


AUDIO_FEATURE_COLUMNS = [
    'acousticness',
    'danceability',
    'energy',
    'instrumentalness',
    'loudness',
    'speechiness',
    'tempo',
    'valence'
]

# Feature weights: Emphasize more important features for music similarity
# Based on research, danceability, energy, and valence are strong indicators of user preference
FEATURE_WEIGHTS = {
    'acousticness': 1.0,
    'danceability': 1.5,      # Higher weight - key for vibe matching
    'energy': 1.5,            # Higher weight - important for mood
    'instrumentalness': 0.8,   # Lower weight - less critical for most users
    'loudness': 0.9,          # Lower weight - preference varies widely
    'speechiness': 0.7,       # Lower weight - only critical for rap/podcasts
    'tempo': 1.2,             # Moderate weight - important for workout/dance music
    'valence': 1.5            # Higher weight - emotional tone is crucial
}


def get_recommendations_ml(sp, top_tracks, top_artists, limit=50):
    """
    Generate music recommendations using ML-based audio feature analysis.

    Algorithm:
    1. Build candidate pool from top artists and related artists
    2. Fetch Spotify audio features for all tracks (user's + candidates)
    3. Apply feature weights to emphasize important attributes
    4. Normalize features using StandardScaler
    5. Calculate weighted cosine similarity between candidates and user preferences
    6. Rank by similarity score with diversity filtering
    7. Return top N recommendations with metadata

    Args:
        sp: Spotipy client
        top_tracks: User's top tracks
        top_artists: User's top artists
        limit: Number of recommendations to return

    Returns:
        List of recommended tracks with metadata
    """

    print("=== ML-Based Recommendation Engine (Spotify Audio Features) ===")

    # 1. Collect user's listening history
    print("Step 1: Collecting user's listening history...")
    user_track_ids = set()

    for rng in ["short_term", "medium_term", "long_term"]:
        try:
            history = sp.current_user_top_tracks(limit=50, time_range=rng)["items"]
            user_track_ids.update([t["id"] for t in history if "id" in t])
        except Exception:
            continue

    try:
        recent = sp.current_user_recently_played(limit=50)["items"]
        user_track_ids.update([r["track"]["id"] for r in recent if "track" in r and "id" in r["track"]])
    except Exception:
        pass

    user_track_ids.update([t["id"] for t in top_tracks if "id" in t])
    print(f"Found {len(user_track_ids)} tracks in user's history")

    # 2. Build candidate pool from top artists (OPTIMIZED: reduced API calls)
    print("\nStep 2: Building candidate pool (optimized for rate limits)...")
    candidates = []

    # REDUCED: Only use top 8 artists (was 15) to minimize Spotify API calls
    for artist in top_artists[:8]:
        try:
            artist_id = artist["id"]

            # Get top tracks from artist (REDUCED: 3 tracks instead of 5)
            try:
                top_tracks_artist = sp.artist_top_tracks(artist_id, country="US")["tracks"][:3]
                for track in top_tracks_artist:
                    if track["id"] not in user_track_ids:
                        candidates.append({
                            "id": track["id"],
                            "name": track["name"],
                            "artist": artist["name"]
                        })
            except Exception as e:
                print(f"Error fetching tracks for artist {artist.get('name', 'unknown')}: {e}")
                continue

            # Get related artists (REDUCED: 2 related artists instead of 3)
            try:
                related = sp.artist_related_artists(artist_id)["artists"][:2]
                for rel in related:
                    try:
                        # REDUCED: 2 tracks per related artist instead of 3
                        rel_tracks = sp.artist_top_tracks(rel["id"], country="US")["tracks"][:2]
                        for track in rel_tracks:
                            if track["id"] not in user_track_ids:
                                candidates.append({
                                    "id": track["id"],
                                    "name": track["name"],
                                    "artist": rel["name"]
                                })
                    except Exception:
                        continue  # Skip problematic artists (404 errors)
            except Exception as e:
                print(f"Error fetching related artists for {artist.get('name', 'unknown')}: {e}")
                continue

        except Exception as e:
            print(f"Error processing artist: {e}")
            continue

    # Remove duplicates
    candidates_df = pd.DataFrame(candidates)
    if not candidates_df.empty:
        candidates_df = candidates_df.drop_duplicates(subset=["id"])
    print(f"Collected {len(candidates_df)} candidate tracks")

    if candidates_df.empty:
        print("No candidates found")
        return []

    # 3. Fetch audio features using Spotify's native API
    print("\nStep 3: Fetching audio features from Spotify...")

    # Get audio features for user's top tracks
    user_top_track_ids = [t["id"] for t in top_tracks[:20]]
    print(f"Fetching features for {len(user_top_track_ids)} user tracks...")

    try:
        user_features_raw = sp.audio_features(user_top_track_ids)
        user_features = {}
        for i, features in enumerate(user_features_raw):
            if features:  # Skip None results
                track_id = user_top_track_ids[i]
                user_features[track_id] = {
                    'acousticness': features.get('acousticness', 0),
                    'danceability': features.get('danceability', 0),
                    'energy': features.get('energy', 0),
                    'instrumentalness': features.get('instrumentalness', 0),
                    'loudness': features.get('loudness', 0),
                    'speechiness': features.get('speechiness', 0),
                    'tempo': features.get('tempo', 0),
                    'valence': features.get('valence', 0)
                }
    except Exception as e:
        print(f"Error fetching user audio features: {e}")
        return []

    # Get audio features for candidate tracks (limit to 100 for performance)
    candidate_track_ids = candidates_df["id"].tolist()[:100]
    print(f"Fetching features for {len(candidate_track_ids)} candidate tracks...")

    try:
        candidate_features_raw = sp.audio_features(candidate_track_ids)
        candidate_features = {}
        for i, features in enumerate(candidate_features_raw):
            if features:  # Skip None results
                track_id = candidate_track_ids[i]
                candidate_features[track_id] = {
                    'acousticness': features.get('acousticness', 0),
                    'danceability': features.get('danceability', 0),
                    'energy': features.get('energy', 0),
                    'instrumentalness': features.get('instrumentalness', 0),
                    'loudness': features.get('loudness', 0),
                    'speechiness': features.get('speechiness', 0),
                    'tempo': features.get('tempo', 0),
                    'valence': features.get('valence', 0)
                }
    except Exception as e:
        print(f"Error fetching candidate audio features: {e}")
        return []

    if not user_features or not candidate_features:
        print("Failed to fetch sufficient audio features")
        return []

    print(f"Successfully fetched features: {len(user_features)} user tracks, {len(candidate_features)} candidates")

    # 4. Build feature matrices with weighted features
    print("\nStep 4: Building weighted feature matrices...")

    # Get weight vector for features
    weight_vector = np.array([FEATURE_WEIGHTS[col] for col in AUDIO_FEATURE_COLUMNS])

    # User features matrix
    user_feature_matrix = []
    user_track_ids_with_features = []
    for track_id, features in user_features.items():
        feature_vector = [features[col] for col in AUDIO_FEATURE_COLUMNS]
        user_feature_matrix.append(feature_vector)
        user_track_ids_with_features.append(track_id)

    # Candidate features matrix
    candidate_feature_matrix = []
    candidate_track_ids_with_features = []
    for track_id, features in candidate_features.items():
        feature_vector = [features[col] for col in AUDIO_FEATURE_COLUMNS]
        candidate_feature_matrix.append(feature_vector)
        candidate_track_ids_with_features.append(track_id)

    if not user_feature_matrix or not candidate_feature_matrix:
        print("Insufficient feature data")
        return []

    user_feature_matrix = np.array(user_feature_matrix)
    candidate_feature_matrix = np.array(candidate_feature_matrix)

    print(f"User features: {user_feature_matrix.shape}")
    print(f"Candidate features: {candidate_feature_matrix.shape}")

    # 5. Normalize features
    print("\nStep 5: Normalizing features...")
    scaler = StandardScaler()
    user_features_scaled = scaler.fit_transform(user_feature_matrix)
    candidate_features_scaled = scaler.transform(candidate_feature_matrix)

    # Apply feature weights after normalization
    print("Applying feature weights...")
    user_features_weighted = user_features_scaled * weight_vector
    candidate_features_weighted = candidate_features_scaled * weight_vector

    # 6. Calculate similarity using weighted cosine similarity
    print("\nStep 6: Calculating weighted similarity scores...")
    similarity_matrix = cosine_similarity(candidate_features_weighted, user_features_weighted)

    # For each candidate, calculate weighted similarity
    # Use max similarity to user's top tracks + average similarity for balanced recommendations
    max_similarities = similarity_matrix.max(axis=1)
    avg_similarities = similarity_matrix.mean(axis=1)

    # Combined score: 70% max similarity (find best match) + 30% average (ensure overall fit)
    combined_similarities = 0.7 * max_similarities + 0.3 * avg_similarities

    # 7. Rank candidates by similarity with diversity
    print("\nStep 7: Ranking recommendations with diversity...")
    recommendations = []

    for i, track_id in enumerate(candidate_track_ids_with_features):
        recommendations.append({
            "track_id": track_id,
            "similarity": float(combined_similarities[i]),
            "max_sim": float(max_similarities[i]),
            "avg_sim": float(avg_similarities[i])
        })

    # Sort by combined similarity score
    recommendations.sort(key=lambda x: x["similarity"], reverse=True)

    # 8. Enrich with Spotify metadata
    print("\nStep 8: Enriching with Spotify metadata...")
    result = []

    for rec in recommendations[:limit * 2]:  # Get extra in case some fail
        try:
            track_id = rec["track_id"]
            track_data = sp.track(track_id)

            result.append({
                "id": track_id,
                "name": track_data["name"],
                "artist": track_data["artists"][0]["name"],
                "score": rec["similarity"],
                "album_image": track_data["album"]["images"][0]["url"] if track_data["album"]["images"] else None,
                "preview_url": track_data.get("preview_url"),
                "source": "ml_audio_features"
            })

            if len(result) >= limit:
                break

        except Exception as e:
            print(f"Error enriching track {rec['track_id']}: {e}")
            continue

    print(f"\n✓ Generated {len(result)} ML-based recommendations using Spotify audio features")
    return result
