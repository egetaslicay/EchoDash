import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


# --- Candidate pool ---
def get_candidate_tracks(sp, top_artists, top_tracks, per_artist=5, per_related=3):
    """
    Build a pool of candidate tracks from user's top artists + related artists.
    Excludes tracks the user already listens to.
    """
    candidates = []

    # Tracks the user already listens to (exclude these)
    user_track_ids = {t["id"] for t in top_tracks if "id" in t}

    for artist in top_artists:
        try:
            artist_id = artist["id"]

            # 1. Get artist’s top tracks
            top_tracks_artist = sp.artist_top_tracks(artist_id, country="US")["tracks"][:per_artist]
            for track in top_tracks_artist:
                if track["id"] not in user_track_ids:
                    candidates.append({
                        "id": track["id"],
                        "name": track["name"],
                        "artist": artist["name"],
                        "source": "top_artist"
                    })

            # 2. Expand to related artists
            related = sp.artist_related_artists(artist_id)["artists"][:per_related]
            for rel in related:
                try:
                    rel_tracks = sp.artist_top_tracks(rel["id"], country="US")["tracks"][:2]
                    for track in rel_tracks:
                        if track["id"] not in user_track_ids:
                            candidates.append({
                                "id": track["id"],
                                "name": track["name"],
                                "artist": rel["name"],
                                "source": "related_artist"
                            })
                except Exception:
                    continue

        except Exception:
            continue

    # Deduplicate by track id
    df = pd.DataFrame(candidates)
    if not df.empty:
        df = df.drop_duplicates(subset=["id"])
    return df


# --- Recommendation engine ---
def recommend_tracks(top_tracks, candidates, top_n=10):
    """
    Recommend tracks using cosine similarity on dummy vectors (stand-in for audio features).
    """
    if candidates is None or candidates.empty:
        return pd.DataFrame()

    # Simulate feature vectors
    rng = np.random.default_rng(seed=42)
    track_vecs = rng.random((len(top_tracks), 10))
    cand_vecs = rng.random((len(candidates), 10))

    sims = cosine_similarity(track_vecs, cand_vecs)
    scores = sims.mean(axis=0)

    candidates = candidates.copy()
    candidates["similarity"] = scores
    return candidates.sort_values("similarity", ascending=False).head(top_n)


def get_recommendations(sp, top_tracks, top_artists, limit=50):
    """
    Generate up to `limit` fresh recommendations:
    - Pulls user's top tracks (all ranges) + recently played
    - Expands candidates with top + related artists
    - Filters out songs the user already knows
    - Ranks & boosts variety
    """
    # Step 1: Collect all known user track IDs (exclude these)
    user_track_ids = set()

    # Top tracks across all ranges
    for rng in ["short_term", "medium_term", "long_term"]:
        try:
            history = sp.current_user_top_tracks(limit=50, time_range=rng)["items"]
            user_track_ids.update([t["id"] for t in history if "id" in t])
        except Exception:
            continue

    # Recently played (safe fallback if scope not granted)
    try:
        recent = sp.current_user_recently_played(limit=50)["items"]
        user_track_ids.update([r["track"]["id"] for r in recent if "track" in r and "id" in r["track"]])
    except Exception:
        # Graceful fallback
        pass

    # Tracks passed directly into the function
    user_track_ids.update([t["id"] for t in top_tracks if "id" in t])

    # Step 2: Build large candidate pool
    candidates = get_candidate_tracks(sp, top_artists, top_tracks, per_artist=15, per_related=20)

    # Step 3: Remove songs user already knows
    candidates = candidates[~candidates["id"].isin(user_track_ids)]

    if candidates.empty:
        return []

    # Step 4: Rank (oversample 3x then cut down to `limit`)
    recs = recommend_tracks(top_tracks, candidates, top_n=limit * 3)

    # Step 5: Diversity weighting (boost related artists)
    recs["similarity"] *= recs["source"].apply(lambda s: 0.8 if s == "top_artist" else 1.2)

    recs = recs.sort_values("similarity", ascending=False).head(limit)

    # Step 6: Enrich with metadata
    result = []
    for _, row in recs.iterrows():
        try:
            track_data = sp.track(row["id"])
            result.append({
                "id": row["id"],
                "name": row["name"],
                "artist": row["artist"],
                "score": float(row["similarity"]),
                "album_image": track_data["album"]["images"][0]["url"] if track_data["album"]["images"] else None,
                "preview_url": track_data.get("preview_url"),
                "source": row.get("source", "unknown")
            })
        except Exception:
            continue

    return result
