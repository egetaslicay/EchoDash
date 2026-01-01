"""
Hybrid Music Recommendation Engine
Combines Spotify's recommendations API + ReccoBeats for best results.
Focuses on artist similarity and audio feature matching.
"""

import requests
import random
import database as db
import numpy as np


def calculate_audio_feature_similarity(user_features, track_features):
    """
    Calculate cosine similarity between user's average features and track features.
    Returns a score between 0 and 1.
    """
    if not user_features or not track_features:
        return 0.0

    # Only compare features that exist in both
    common_keys = set(user_features.keys()) & set(track_features.keys())
    if not common_keys:
        return 0.0

    user_vec = [user_features[k] for k in common_keys]
    track_vec = [track_features[k] for k in common_keys]

    # Cosine similarity
    dot_product = sum(u * t for u, t in zip(user_vec, track_vec))
    user_norm = sum(u ** 2 for u in user_vec) ** 0.5
    track_norm = sum(t ** 2 for t in track_vec) ** 0.5

    if user_norm == 0 or track_norm == 0:
        return 0.0

    return dot_product / (user_norm * track_norm)


def get_spotify_recommendations(sp, seed_track_ids, seed_artist_ids, limit=50):
    """
    Get recommendations from Spotify's API using seed tracks and artists.
    Uses randomized seeds for variety.
    """
    recommendations = []

    try:
        # RANDOMIZE seeds every time for variety!
        # Use different seeds on each request
        import time
        random.seed(time.time())  # Use current time for true randomness

        available_tracks = seed_track_ids[:20]  # Use top 20 tracks
        available_artists = seed_artist_ids[:20]  # Use top 20 artists

        # Randomly select 3 tracks and 2 artists
        tracks_to_use = random.sample(available_tracks, min(3, len(available_tracks)))
        artists_to_use = random.sample(available_artists, min(2, len(available_artists)))

        print(f"    Calling Spotify recommendations API...")
        print(f"      Using {len(tracks_to_use)} random track seeds, {len(artists_to_use)} random artist seeds")

        response = sp.recommendations(
            seed_tracks=tracks_to_use,
            seed_artists=artists_to_use,
            limit=limit,
            market='US'
        )

        tracks = response.get('tracks', [])
        print(f"    ✓ Retrieved {len(tracks)} from Spotify API")

        for track in tracks:
            recommendations.append({
                'id': track['id'],
                'name': track['name'],
                'artist_id': track['artists'][0]['id'] if track['artists'] else None,
                'artist_name': track['artists'][0]['name'] if track['artists'] else '',
                'popularity': track.get('popularity', 50),
                'album_image': track['album']['images'][0]['url'] if track.get('album', {}).get('images') else None,
                'preview_url': track.get('preview_url'),
                'source': 'Spotify API'
            })

    except Exception as e:
        print(f"    ⚠️ Spotify recommendations failed: {e}")

    return recommendations


def get_reccobeats_recommendations(seed_track_ids, limit=30, batch_num=0):
    """
    Get recommendations from ReccoBeats API.
    Uses randomized seeds for variety.
    """
    recommendations = []

    try:
        # RANDOMIZE seeds every time for variety!
        import time
        random.seed(time.time() + batch_num)  # Use time + batch for unique seeds

        available_tracks = seed_track_ids[:30]  # Use top 30 tracks
        seeds_to_use = random.sample(available_tracks, min(5, len(available_tracks)))

        print(f"    Calling ReccoBeats API (batch {batch_num + 1})...")
        url = "https://api.reccobeats.com/v1/track/recommendation"
        params = [('seeds', seed_id) for seed_id in seeds_to_use]
        params.append(('size', limit))

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            tracks = data.get('content', []) if isinstance(data, dict) else data

            print(f"    ✓ Retrieved {len(tracks)} from ReccoBeats")

            for track in tracks:
                spotify_href = track.get('href', '')
                if '/track/' in spotify_href:
                    spotify_id = spotify_href.split('/track/')[-1].split('?')[0]
                    recommendations.append({
                        'id': spotify_id,
                        'name': track.get('trackTitle', ''),
                        'artist_name': track['artists'][0]['name'] if track.get('artists') else '',
                        'popularity': track.get('popularity', 50),
                        'source': 'ReccoBeats API'
                    })

    except Exception as e:
        print(f"    ⚠️ ReccoBeats failed: {e}")

    return recommendations


def get_recommendations_hybrid(sp, top_tracks, top_artists, limit=50, user_id=None):
    """
    Hybrid recommendation engine combining Spotify + ReccoBeats.
    Focuses heavily on artist similarity and audio features.
    """

    print("=== Hybrid Recommendations (Spotify + ReccoBeats) ===")

    # 0. Get user feedback and history
    liked_track_ids = set()
    disliked_track_ids = set()
    recently_recommended_ids = set()

    if user_id:
        print("Step 0: Loading user feedback and history...")
        liked_tracks = db.get_liked_tracks(user_id)
        liked_track_ids = {t['track_id'] for t in liked_tracks}
        disliked_track_ids = {t['track_id'] for t in db.get_disliked_tracks(user_id)}
        recently_recommended_ids = db.get_recently_recommended_track_ids(user_id, days=3)
        print(f"  Excluding {len(liked_track_ids) + len(disliked_track_ids) + len(recently_recommended_ids)} tracks")

    # 1. Build user profile
    print("\nStep 1: Building user profile...")
    seed_track_ids = [t["id"] for t in top_tracks[:50] if "id" in t]
    seed_artist_ids = [a["id"] for a in top_artists[:50] if "id" in a]
    user_artist_ids = set(seed_artist_ids)

    # Get user's favorite genres
    user_genres = set()
    for artist in top_artists[:30]:
        user_genres.update(artist.get("genres", []))

    print(f"  Profile: {len(seed_track_ids)} tracks, {len(seed_artist_ids)} artists, {len(user_genres)} genres")

    # 2. Get average audio features from user's top tracks
    print("\nStep 2: Analyzing audio preferences...")
    user_audio_features = {}
    try:
        # Get audio features from Spotify
        features_data = sp.audio_features(seed_track_ids[:20])
        valid_features = [f for f in features_data if f is not None]

        if valid_features:
            feature_keys = ['danceability', 'energy', 'valence', 'acousticness', 'instrumentalness']
            for key in feature_keys:
                values = [f[key] for f in valid_features if key in f]
                if values:
                    user_audio_features[key] = sum(values) / len(values)

            print(f"  ✓ Analyzed {len(valid_features)} tracks")
            print(f"    Avg: energy={user_audio_features.get('energy', 0):.2f}, "
                  f"dance={user_audio_features.get('danceability', 0):.2f}")
    except Exception as e:
        print(f"  ⚠️ Could not get Spotify audio features: {e}")

    # 3. Get recommendations from BOTH sources (MORE ReccoBeats, LESS Spotify)
    print("\nStep 3: Fetching recommendations from multiple sources...")

    all_recommendations = []
    seen_ids = set()

    # Get LESS from Spotify (20 tracks) - reduces Spotify bias
    spotify_recs = get_spotify_recommendations(sp, seed_track_ids, seed_artist_ids, limit=20)
    for rec in spotify_recs:
        if rec['id'] not in seen_ids:
            all_recommendations.append(rec)
            seen_ids.add(rec['id'])

    # Get MORE from ReccoBeats with MULTIPLE batches (60+ tracks total)
    # Each batch uses different random seeds for MAXIMUM variety
    for batch in range(3):  # 3 batches
        recco_recs = get_reccobeats_recommendations(seed_track_ids, limit=25, batch_num=batch)
        for rec in recco_recs:
            if rec['id'] not in seen_ids:
                all_recommendations.append(rec)
                seen_ids.add(rec['id'])

    print(f"\n  Total candidates: {len(all_recommendations)}")

    if not all_recommendations:
        print("  ❌ No recommendations found")
        return []

    # 4. Enrich with full track data and score
    print("\nStep 4: Scoring recommendations (artist + audio focused)...")

    enriched_recommendations = []
    artist_match_count = 0
    filtered_count = 0

    for rec in all_recommendations:
        track_id = rec['id']

        # Filter out already known tracks
        if (track_id in liked_track_ids or
            track_id in disliked_track_ids or
            track_id in recently_recommended_ids):
            filtered_count += 1
            continue

        try:
            # Get full track details
            track = sp.track(track_id)
            artist_id = track['artists'][0]['id'] if track['artists'] else None
            artist_name = track['artists'][0]['name'] if track['artists'] else ''

            # Get artist genres
            artist_genres = []
            if artist_id:
                try:
                    artist_info = sp.artist(artist_id)
                    artist_genres = artist_info.get('genres', [])
                except:
                    pass

            # Get audio features for this track
            track_audio_features = {}
            try:
                features = sp.audio_features([track_id])[0]
                if features:
                    track_audio_features = {
                        'danceability': features.get('danceability', 0),
                        'energy': features.get('energy', 0),
                        'valence': features.get('valence', 0),
                        'acousticness': features.get('acousticness', 0),
                        'instrumentalness': features.get('instrumentalness', 0)
                    }
            except:
                pass

            # === SCORING ===
            score = 0.0

            # SAME ARTIST MATCH (40% weight!) - This is what makes recommendations relevant
            if artist_id in user_artist_ids:
                score += 0.4
                artist_match_count += 1

            # GENRE OVERLAP (30% weight)
            if artist_genres and user_genres:
                genre_overlap = len(set(artist_genres) & user_genres)
                if genre_overlap > 0:
                    score += 0.3 * (genre_overlap / max(len(user_genres), 1))

            # AUDIO FEATURE SIMILARITY (20% weight)
            if user_audio_features and track_audio_features:
                similarity = calculate_audio_feature_similarity(user_audio_features, track_audio_features)
                score += 0.2 * similarity

            # POPULARITY (5% weight)
            score += 0.05 * (track.get('popularity', 0) / 100.0)

            # SOURCE BONUS (2% weight) - Small preference for quality sources
            if rec.get('source') == 'Spotify API':
                score += 0.02

            # Add LARGER randomization for more variety
            score += random.uniform(-0.08, 0.08)

            enriched_recommendations.append({
                'id': track_id,
                'name': track['name'],
                'artist': artist_name,
                'artist_id': artist_id,
                'genres': artist_genres,
                'popularity': track.get('popularity', 50),
                'album_image': track['album']['images'][0]['url'] if track.get('album', {}).get('images') else None,
                'preview_url': track.get('preview_url'),
                'score': score,
                'source': rec.get('source', 'Unknown')
            })

        except Exception as e:
            # Skip tracks that fail
            continue

    print(f"    Artist matches: {artist_match_count}/{len(enriched_recommendations)} "
          f"({artist_match_count/max(len(enriched_recommendations), 1)*100:.1f}%)")
    print(f"    Filtered out: {filtered_count} duplicate/known tracks")

    if not enriched_recommendations:
        return []

    # Sort by score
    enriched_recommendations.sort(key=lambda x: x['score'], reverse=True)

    # Filter by minimum quality
    min_score = 0.2  # At least 20% match
    quality_recs = [r for r in enriched_recommendations if r['score'] >= min_score]

    if len(quality_recs) < len(enriched_recommendations):
        print(f"    Filtered {len(enriched_recommendations) - len(quality_recs)} low-quality recs")

    # Apply diversity (max 2 per artist)
    print("\nStep 5: Applying diversity filters...")
    final_recs = []
    artist_counts = {}

    for rec in quality_recs:
        artist_id = rec['artist_id']
        if artist_id and artist_counts.get(artist_id, 0) >= 2:
            continue

        final_recs.append({
            'id': rec['id'],
            'name': rec['name'],
            'artist': rec['artist'],
            'album_image': rec['album_image'],
            'preview_url': rec['preview_url'],
            'score': round(rec['score'], 3),
            'source': rec['source']
        })

        if artist_id:
            artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1

        if len(final_recs) >= limit:
            break

    print(f"\n✓ Generated {len(final_recs)} high-quality recommendations")
    print(f"  Sources: Spotify={sum(1 for r in final_recs if r['source']=='Spotify API')}, "
          f"ReccoBeats={sum(1 for r in final_recs if r['source']=='ReccoBeats API')}")

    return final_recs
