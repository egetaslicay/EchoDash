"""
ML-based Music Recommendation Engine
Uses artist similarity, genre matching, and popularity scoring.
Incorporates user feedback (likes/dislikes) for personalization.
Note: Audio features API was deprecated by Spotify.
"""

import numpy as np
import pandas as pd
from typing import List, Dict
import database as db


def get_recommendations_ml(sp, top_tracks, top_artists, limit=50, user_id=None):
    """
    Generate music recommendations using artist similarity and genre matching.

    Algorithm:
    1. Build candidate pool from top artists and related artists
    2. Extract user's preferred genres from top artists
    3. Score candidates based on:
       - Artist popularity match
       - Genre overlap
       - Diversity (avoid same artist)
    4. Rank and return top recommendations

    Args:
        sp: Spotipy client
        top_tracks: User's top tracks
        top_artists: User's top artists
        limit: Number of recommendations to return

    Returns:
        List of recommended tracks with metadata
    """

    print("=== Genre & Artist-Based Recommendation Engine ===")

    # 0. Get user feedback if available
    user_feedback = {}
    liked_tracks = []
    disliked_track_ids = set()

    if user_id:
        print("Step 0: Loading user feedback...")
        user_feedback = db.get_user_feedback(user_id)
        liked_tracks = db.get_liked_tracks(user_id)
        disliked_track_ids = {t['track_id'] for t in db.get_disliked_tracks(user_id)}
        print(f"  Found {len(liked_tracks)} liked tracks and {len(disliked_track_ids)} disliked tracks")

    # 1. Collect user's listening history
    print("\nStep 1: Collecting user's listening history...")
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

    # 2. Extract user's preferred genres
    print("\nStep 2: Analyzing user's genre preferences...")
    user_genres = {}
    user_artist_ids = set()

    for artist in top_artists:
        user_artist_ids.add(artist["id"])
        for genre in artist.get("genres", []):
            user_genres[genre] = user_genres.get(genre, 0) + 1

    print(f"User enjoys {len(user_genres)} genres: {', '.join(list(user_genres.keys())[:5])}...")

    # 3. Build candidate pool from related artists
    print("\nStep 3: Building candidate pool from related artists...")
    candidates = []

    for artist in top_artists[:10]:
        try:
            artist_id = artist["id"]

            # Get top tracks from artist
            try:
                top_tracks_artist = sp.artist_top_tracks(artist_id, country="US")["tracks"][:3]
                for track in top_tracks_artist:
                    track_id = track["id"]
                    # Exclude tracks already in user's library or disliked
                    if track_id not in user_track_ids and track_id not in disliked_track_ids:
                        candidates.append({
                            "id": track_id,
                            "name": track["name"],
                            "artist": artist["name"],
                            "artist_id": artist_id,
                            "popularity": track.get("popularity", 50),
                            "album_image": track["album"]["images"][0]["url"] if track.get("album", {}).get("images") else None,
                            "preview_url": track.get("preview_url"),
                            "is_favorite_artist": True
                        })
            except Exception as e:
                print(f"  Error fetching tracks for {artist.get('name', 'unknown')}: {e}")
                continue

            # Get related artists
            try:
                related = sp.artist_related_artists(artist_id)["artists"][:3]
                for rel in related:
                    try:
                        rel_tracks = sp.artist_top_tracks(rel["id"], country="US")["tracks"][:2]
                        for track in rel_tracks:
                            track_id = track["id"]
                            # Exclude tracks already in user's library or disliked
                            if track_id not in user_track_ids and track_id not in disliked_track_ids:
                                candidates.append({
                                    "id": track_id,
                                    "name": track["name"],
                                    "artist": rel["name"],
                                    "artist_id": rel["id"],
                                    "popularity": track.get("popularity", 50),
                                    "album_image": track["album"]["images"][0]["url"] if track.get("album", {}).get("images") else None,
                                    "preview_url": track.get("preview_url"),
                                    "genres": rel.get("genres", []),
                                    "is_favorite_artist": False
                                })
                    except Exception:
                        continue
            except Exception as e:
                print(f"  Error fetching related artists for {artist.get('name', 'unknown')}: {e}")
                continue

        except Exception as e:
            print(f"  Error processing artist: {e}")
            continue

    # Remove duplicates
    candidates_df = pd.DataFrame(candidates)
    if not candidates_df.empty:
        candidates_df = candidates_df.drop_duplicates(subset=["id"])
    print(f"Collected {len(candidates_df)} candidate tracks")

    if candidates_df.empty:
        print("No candidates found")
        return []

    # 4. Score candidates based on genre match, popularity, and user feedback
    print("\nStep 4: Scoring candidates (with user feedback)...")
    scores = []

    # Extract liked track artists for boosting
    liked_artists = set()
    liked_genres = set()
    if liked_tracks:
        for liked in liked_tracks:
            # Extract artist from "Artist - Track" format if stored that way
            artist = liked.get('artist_name', '')
            if artist:
                liked_artists.add(artist)

    for _, track in candidates_df.iterrows():
        score = 0.0

        # Base score from popularity (normalized 0-1)
        popularity_score = track["popularity"] / 100.0
        score += popularity_score * 0.3

        # Genre matching bonus
        track_genres = track.get("genres", [])
        if track_genres:
            genre_overlap = len(set(track_genres) & set(user_genres.keys()))
            genre_score = min(genre_overlap / len(user_genres), 1.0) if user_genres else 0
            score += genre_score * 0.5

        # Favorite artist bonus
        if track.get("is_favorite_artist", False):
            score += 0.2

        # User feedback bonus: boost if artist matches liked tracks
        if liked_artists and track["artist"] in liked_artists:
            score += 0.25
            print(f"  ⭐ Boosted {track['name']} - artist match with liked tracks")

        scores.append(score)

    candidates_df["score"] = scores

    # 5. Rank and filter for diversity
    print("\nStep 5: Ranking and filtering for diversity...")
    recommendations = []
    seen_artists = set()
    max_per_artist = 2
    artist_counts = {}

    # Sort by score
    candidates_df = candidates_df.sort_values("score", ascending=False)

    for _, track in candidates_df.iterrows():
        artist_id = track["artist_id"]

        # Diversity filter: limit tracks per artist
        if artist_counts.get(artist_id, 0) >= max_per_artist:
            continue

        recommendations.append({
            "id": track["id"],
            "name": track["name"],
            "artist": track["artist"],
            "album_image": track.get("album_image"),
            "preview_url": track.get("preview_url"),
            "score": round(track["score"], 3),
            "source": "ML Genre Match" if track.get("genres") else "ML Artist Match"
        })

        artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1

        if len(recommendations) >= limit:
            break

    print(f"\n✓ Generated {len(recommendations)} recommendations")
    return recommendations
