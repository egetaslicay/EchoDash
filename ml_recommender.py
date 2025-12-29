"""
ML-based Music Recommendation Engine
Uses audio features (acousticness, danceability, energy, etc.)
with KNN and cosine similarity for recommendations.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict
from audio_features_service import get_audio_features_service


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


def get_recommendations_ml(sp, top_tracks, top_artists, limit=50):
    """
    Generate music recommendations using ML-based audio feature analysis.

    Algorithm:
    1. Get candidate tracks from top artists and related artists
    2. Fetch audio features for all tracks (user's + candidates)
    3. Normalize features using StandardScaler
    4. Use KNN to find tracks similar to user's top tracks
    5. Rank by similarity score and return top N

    Args:
        sp: Spotipy client
        top_tracks: User's top tracks
        top_artists: User's top artists
        limit: Number of recommendations to return

    Returns:
        List of recommended tracks with metadata
    """

    print("=== ML-Based Recommendation Engine ===")

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

    # 2. Build candidate pool from top artists and related artists
    print("\nStep 2: Building candidate pool...")
    candidates = []

    for artist in top_artists[:15]:  # Use top 15 artists
        try:
            artist_id = artist["id"]

            # Get top tracks from artist
            top_tracks_artist = sp.artist_top_tracks(artist_id, country="US")["tracks"][:5]
            for track in top_tracks_artist:
                if track["id"] not in user_track_ids:
                    candidates.append({
                        "id": track["id"],
                        "name": track["name"],
                        "artist": artist["name"]
                    })

            # Get related artists
            related = sp.artist_related_artists(artist_id)["artists"][:3]
            for rel in related:
                try:
                    rel_tracks = sp.artist_top_tracks(rel["id"], country="US")["tracks"][:3]
                    for track in rel_tracks:
                        if track["id"] not in user_track_ids:
                            candidates.append({
                                "id": track["id"],
                                "name": track["name"],
                                "artist": rel["name"]
                            })
                except Exception:
                    continue

        except Exception as e:
            print(f"Error processing artist: {e}")
            continue

    # Remove duplicates
    candidates_df = pd.DataFrame(candidates).drop_duplicates(subset=["id"])
    print(f"Collected {len(candidates_df)} candidate tracks")

    if candidates_df.empty:
        print("No candidates found")
        return []

    # 3. Fetch audio features
    print("\nStep 3: Fetching audio features...")
    try:
        audio_service = get_audio_features_service()
    except ValueError as e:
        print(f"Audio features service not available: {e}")
        print("Please set RAPID_API_KEY in .env file")
        return []

    # Get audio features for user's top tracks
    user_top_track_ids = [t["id"] for t in top_tracks[:20]]  # Use top 20 for analysis
    user_features = audio_service.get_audio_features_batch(user_top_track_ids)

    # Get audio features for candidate tracks
    candidate_track_ids = candidates_df["id"].tolist()[:200]  # Limit to 200 to avoid excessive API calls
    candidate_features = audio_service.get_audio_features_batch(candidate_track_ids)

    if not user_features or not candidate_features:
        print("Failed to fetch audio features")
        return []

    # 4. Build feature matrices
    print("\nStep 4: Building feature matrices...")

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

    # 6. Calculate similarity using cosine similarity
    print("\nStep 6: Calculating similarity scores...")
    similarity_matrix = cosine_similarity(candidate_features_scaled, user_features_scaled)

    # For each candidate, take the max similarity to any of user's top tracks
    max_similarities = similarity_matrix.max(axis=1)

    # 7. Rank candidates by similarity
    print("\nStep 7: Ranking recommendations...")
    recommendations = []

    for i, track_id in enumerate(candidate_track_ids_with_features):
        recommendations.append({
            "track_id": track_id,
            "similarity": float(max_similarities[i])
        })

    # Sort by similarity
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

    print(f"\n✓ Generated {len(result)} ML-based recommendations")
    return result


def get_recommendations_knn(sp, top_tracks, top_artists, limit=50, n_neighbors=10):
    """
    Alternative: KNN-based recommendations.
    Similar to get_recommendations_ml but uses KNN instead of cosine similarity.
    """

    print("=== KNN-Based Recommendation Engine ===")
    print(f"Using {n_neighbors} nearest neighbors")

    # Steps 1-5 are the same as get_recommendations_ml
    # (Code omitted for brevity - implement if needed)

    # Use KNN for finding similar tracks
    # knn = NearestNeighbors(n_neighbors=n_neighbors, metric='cosine')
    # knn.fit(candidate_features_scaled)
    # ...

    pass  # Implement if needed
