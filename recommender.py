import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from lastfm_service import get_lastfm_service
from ml_recommender import get_recommendations_ml



def get_candidate_tracks(sp, top_artists, top_tracks, per_artist=5, per_related=3):
    """
    Build a pool of candidate tracks from user's top artists + related artists.
    Excludes tracks the user already listens to.
    """
    candidates = []

 
    user_track_ids = {t["id"] for t in top_tracks if "id" in t}

    for artist in top_artists:
        try:
            artist_id = artist["id"]

            
            top_tracks_artist = sp.artist_top_tracks(artist_id, country="US")["tracks"][:per_artist]
            for track in top_tracks_artist:
                if track["id"] not in user_track_ids:
                    candidates.append({
                        "id": track["id"],
                        "name": track["name"],
                        "artist": artist["name"],
                        "source": "top_artist"
                    })

           
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

   
    df = pd.DataFrame(candidates)
    if not df.empty:
        df = df.drop_duplicates(subset=["id"])
    return df



def recommend_tracks(top_tracks, candidates, top_n=10):
    """
    Recommend tracks using cosine similarity on dummy vectors (stand-in for audio features).
    """
    if candidates is None or candidates.empty:
        return pd.DataFrame()

   
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
    Generate up to `limit` fresh recommendations using ML-based audio feature analysis.

    Recommendation Strategy (in order of priority):
    1. ML-based: Uses audio features (acousticness, danceability, energy, etc.)
       with cosine similarity to find tracks similar to user's taste
    2. Last.fm: Collaborative filtering based on similar tracks/artists
    3. Fallback: Basic recommendation using Spotify's related artists

    Args:
        sp: Spotipy client
        top_tracks: User's top tracks
        top_artists: User's top artists
        limit: Number of recommendations to return

    Returns:
        List of recommended tracks with metadata
    """

    # Try ML-based recommendations first (best quality)
    try:
        print("Attempting ML-based recommendations using audio features...")
        recommendations = get_recommendations_ml(sp, top_tracks, top_artists, limit)
        if recommendations:
            return recommendations
        print("ML recommendations returned empty, trying fallback...")
    except Exception as e:
        print(f"ML recommender not available: {e}")
        print("Falling back to Last.fm...")

    # Try Last.fm collaborative filtering
    try:
        lastfm = get_lastfm_service()
        return _get_recommendations_lastfm(sp, top_tracks, top_artists, limit, lastfm)
    except ValueError as e:
        print(f"Last.fm service not available: {e}")
        # Fallback to basic method if Last.fm is not configured
        return _get_recommendations_fallback(sp, top_tracks, top_artists, limit)



def _get_recommendations_lastfm(sp, top_tracks, top_artists, limit, lastfm):
    """
    Last.fm-based recommendations using collaborative filtering.
    """
    print("Using Last.fm collaborative filtering...")

    # Collect all user's known track IDs
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

    # Collect recommendations from Last.fm
    recommendations = []

    # 1. Get similar tracks for user's top tracks
    print("Getting similar tracks from Last.fm...")
    for track in top_tracks[:10]:  # Use top 10 tracks
        try:
            track_name = track.get("name", "")
            artist_name = track["artists"][0]["name"] if track.get("artists") else ""

            if not track_name or not artist_name:
                continue

            similar_tracks = lastfm.get_similar_tracks(track_name, artist_name, limit=5)

            for similar in similar_tracks:
                recommendations.append({
                    "name": similar["name"],
                    "artist": similar["artist"],
                    "score": similar["match_score"],
                    "source": "similar_track"
                })
        except Exception as e:
            print(f"Error getting similar tracks: {e}")
            continue

    # 2. Get similar artists and their top tracks
    print("Getting similar artists from Last.fm...")
    for artist in top_artists[:10]:  # Use top 10 artists
        try:
            artist_name = artist.get("name", "")
            if not artist_name:
                continue

            # Get similar artists
            similar_artists = lastfm.get_similar_artists(artist_name, limit=3)

            for similar_artist in similar_artists:
                # Get top tracks from similar artist
                top_tracks_artist = lastfm.get_artist_top_tracks(similar_artist["name"], limit=2)

                for track in top_tracks_artist:
                    recommendations.append({
                        "name": track["name"],
                        "artist": track["artist"],
                        "score": similar_artist["match_score"] * 0.8,  # Slightly lower weight
                        "source": "similar_artist"
                    })
        except Exception as e:
            print(f"Error getting similar artists: {e}")
            continue

    # Remove duplicates and sort by score
    df = pd.DataFrame(recommendations)

    if df.empty:
        print("No recommendations found from Last.fm")
        return []

    # Remove duplicate tracks (same name + artist combo)
    df = df.drop_duplicates(subset=["name", "artist"])

    # Sort by score
    df = df.sort_values("score", ascending=False)

    # Search tracks on Spotify and enrich with metadata
    print(f"Searching {len(df)} recommendations on Spotify...")
    result = []
    seen_spotify_ids = set()

    for _, row in df.iterrows():
        try:
            # Search for track on Spotify
            query = f"track:{row['name']} artist:{row['artist']}"
            search_results = sp.search(q=query, type='track', limit=1)

            if not search_results['tracks']['items']:
                continue

            track_data = search_results['tracks']['items'][0]
            track_id = track_data['id']

            # Skip if already in user's library or already added
            if track_id in user_track_ids or track_id in seen_spotify_ids:
                continue

            seen_spotify_ids.add(track_id)

            result.append({
                "id": track_id,
                "name": track_data["name"],
                "artist": track_data["artists"][0]["name"],
                "score": float(row["score"]),
                "album_image": track_data["album"]["images"][0]["url"] if track_data["album"]["images"] else None,
                "preview_url": track_data.get("preview_url"),
                "source": row["source"]
            })

            # Stop when we have enough recommendations
            if len(result) >= limit:
                break

        except Exception as e:
            print(f"Error enriching track '{row['name']}': {e}")
            continue

    print(f"Found {len(result)} unique recommendations")
    return result


def _get_recommendations_fallback(sp, top_tracks, top_artists, limit=50):
    """
    Fallback recommendation method using the old approach.
    Used when Last.fm API is not configured.
    """
    print("Using fallback recommendation method (Last.fm not configured)")

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

    candidates = get_candidate_tracks(sp, top_artists, top_tracks, per_artist=15, per_related=20)

    candidates = candidates[~candidates["id"].isin(user_track_ids)]

    if candidates.empty:
        return []

    recs = recommend_tracks(top_tracks, candidates, top_n=limit * 3)

    recs["similarity"] *= recs["source"].apply(lambda s: 0.8 if s == "top_artist" else 1.2)

    recs = recs.sort_values("similarity", ascending=False).head(limit)

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
