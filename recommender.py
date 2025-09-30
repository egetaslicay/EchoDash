import random

def pick_seeds(top_tracks, top_artists, max_seeds=5, user_id=None):
    """Pick up to 5 seeds total (mix of tracks + artists)."""
    seeds = []
    track_seeds = [t["id"] for t in top_tracks[:3] if t.get("id")]
    artist_seeds = [a["id"] for a in top_artists[:3] if a.get("id")]
    seeds.extend(track_seeds)
    seeds.extend(artist_seeds)

    if user_id:
        random.seed(user_id)
    random.shuffle(seeds)

    return seeds[:max_seeds]

def get_recommendations(sp, top_tracks, top_artists, limit=10):
    """Use Spotify’s recommendation API directly, no re-ranking."""
    seeds = pick_seeds(top_tracks, top_artists, max_seeds=5)
    track_ids = [s for s in seeds if any(t["id"] == s for t in top_tracks)]
    artist_ids = [s for s in seeds if any(a["id"] == s for a in top_artists)]

    print("➡️ [DEBUG] Seeds chosen:", seeds)
    print("➡️ [DEBUG] Track seeds:", track_ids)
    print("➡️ [DEBUG] Artist seeds:", artist_ids)

    params = {
        "limit": limit,
        "seed_tracks": track_ids[:5] if track_ids else None,
        "seed_artists": artist_ids[:5] if artist_ids else None,
        "seed_genres": ["pop", "rock"]  # always include fallback
    }

    print("➡️ [DEBUG] Sending params to Spotify:", params)

    try:
        recs = sp.recommendations(
            seed_tracks=params["seed_tracks"],
            seed_artists=params["seed_artists"],
            seed_genres=params["seed_genres"],
            limit=params["limit"]
        )
        tracks = recs.get("tracks", [])
        print(f"✅ [DEBUG] Got {len(tracks)} tracks back from Spotify")
        return tracks
    except Exception as e:
        print("❌ [ERROR] Spotify recs request failed:", e)
        return []
