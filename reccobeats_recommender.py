"""
ReccoBeats-based Music Recommendation Engine
Uses ReccoBeats API for track recommendations instead of Spotify's recommendations API.
ReccoBeats is a free music recommendation service that accepts Spotify track IDs as seeds.
"""

import requests
import random
import database as db


def get_recommendations_reccobeats(sp, top_tracks, top_artists, limit=50, user_id=None):
    """
    Generate music recommendations using ReccoBeats API.

    Algorithm:
    1. Get user's top track IDs as seeds
    2. Make multiple calls to ReccoBeats with different random seed combinations
    3. Filter out duplicates, liked/disliked tracks
    4. Return diverse recommendations

    Args:
        sp: Spotipy client (used for getting user's top tracks)
        top_tracks: User's top tracks (with Spotify IDs)
        top_artists: User's top artists
        limit: Number of recommendations to return
        user_id: User ID for feedback and history

    Returns:
        List of recommended tracks with metadata
    """

    print("=== ReccoBeats Recommendations API Engine ===")

    # 0. Get user feedback and recommendation history
    liked_track_ids = set()
    disliked_track_ids = set()
    recently_recommended_ids = set()

    if user_id:
        print("Step 0: Loading user feedback and history...")
        liked_tracks = db.get_liked_tracks(user_id)
        liked_track_ids = {t['track_id'] for t in liked_tracks}
        disliked_track_ids = {t['track_id'] for t in db.get_disliked_tracks(user_id)}
        recently_recommended_ids = db.get_recently_recommended_track_ids(user_id, days=3)
        print(f"  Found {len(liked_track_ids)} liked and {len(disliked_track_ids)} disliked tracks")
        print(f"  Excluding {len(recently_recommended_ids)} recently recommended tracks")

    # 1. Build seed pool from user's top tracks
    print("\nStep 1: Building seed pool from top tracks...")
    seed_track_ids = [t["id"] for t in top_tracks[:100] if "id" in t]

    if not seed_track_ids:
        print("  ❌ No seed tracks available")
        return []

    print(f"  Seed pool: {len(seed_track_ids)} tracks")

    # 2. Make multiple ReccoBeats API calls with different seed combinations
    print("\nStep 2: Generating recommendations from ReccoBeats...")
    all_recommendations = []
    seen_track_ids = set()
    filtered_count = 0

    # Calculate how many batches needed
    # ReccoBeats accepts multiple seeds, we'll use 5 per batch for variety
    batches_needed = max(5, (limit // 10) + 2)
    seeds_per_batch = 5

    for batch in range(batches_needed):
        try:
            # Randomly select seeds for this batch
            if len(seed_track_ids) < seeds_per_batch:
                batch_seeds = seed_track_ids
            else:
                batch_seeds = random.sample(seed_track_ids, seeds_per_batch)

            print(f"\n  Batch {batch + 1}/{batches_needed}:")
            print(f"    Using {len(batch_seeds)} seed tracks")

            # Call ReccoBeats API
            reccobeats_url = "https://api.reccobeats.com/v1/track/recommendation"

            # Build query parameters - ReccoBeats accepts repeated 'seeds' parameters
            params = [('seeds', seed_id) for seed_id in batch_seeds]
            params.append(('size', 20))  # Get 20 recommendations per batch

            print(f"    Calling ReccoBeats API...")
            response = requests.get(reccobeats_url, params=params, timeout=10)

            if response.status_code != 200:
                print(f"    ❌ ReccoBeats API error: {response.status_code}")
                print(f"       Response: {response.text[:200]}")
                continue

            response_data = response.json()

            # ReccoBeats returns {"content": [...]} format
            if isinstance(response_data, dict):
                recommendations = response_data.get('content', [])
                if not recommendations:
                    print(f"    ❌ No 'content' in response or empty. Keys: {list(response_data.keys())}")
                    continue
            elif isinstance(response_data, list):
                # Fallback if API returns array directly
                recommendations = response_data
            else:
                print(f"    ❌ Unexpected response format: {type(response_data)}")
                continue

            print(f"    ✓ Retrieved {len(recommendations)} recommendations from ReccoBeats")

            # Debug: Show first track structure
            if recommendations and len(recommendations) > 0:
                print(f"    Sample track keys: {list(recommendations[0].keys())[:10]}")

            # Process each recommended track
            for rec_track in recommendations:
                # ReccoBeats returns tracks with Spotify IDs in 'href'
                # Extract Spotify ID from the track data
                track_id = rec_track.get('id')  # ReccoBeats ID
                spotify_href = rec_track.get('href', '')

                # Extract Spotify ID from href (e.g., https://open.spotify.com/track/SPOTIFY_ID)
                if '/track/' in spotify_href:
                    spotify_id = spotify_href.split('/track/')[-1].split('?')[0]
                else:
                    # Skip if we can't get Spotify ID
                    continue

                # Skip duplicates
                if spotify_id in seen_track_ids:
                    continue

                # Filter out liked, disliked, and recently recommended
                if (spotify_id in liked_track_ids or
                    spotify_id in disliked_track_ids or
                    spotify_id in recently_recommended_ids):
                    filtered_count += 1
                    continue

                # Get full track details from Spotify to ensure we have complete metadata
                try:
                    spotify_track = sp.track(spotify_id)

                    seen_track_ids.add(spotify_id)
                    all_recommendations.append({
                        'id': spotify_id,
                        'name': spotify_track['name'],
                        'artist': ', '.join([a['name'] for a in spotify_track['artists']]),
                        'artist_id': spotify_track['artists'][0]['id'] if spotify_track['artists'] else None,
                        'popularity': spotify_track.get('popularity', rec_track.get('popularity', 50)),
                        'album_image': spotify_track['album']['images'][0]['url'] if spotify_track.get('album', {}).get('images') else None,
                        'preview_url': spotify_track.get('preview_url'),
                        'batch': batch
                    })
                except Exception as track_error:
                    print(f"    Warning: Could not fetch Spotify details for {spotify_id}: {track_error}")
                    continue

            # Stop if we have enough recommendations
            if len(all_recommendations) >= limit * 1.5:
                break

        except requests.RequestException as e:
            print(f"  ❌ Network error in batch {batch + 1}: {e}")
            continue
        except Exception as e:
            print(f"  ❌ ERROR in batch {batch + 1}: {type(e).__name__}: {e}")
            continue

    print(f"\n  Total collected: {len(all_recommendations)} unique tracks")
    if filtered_count > 0:
        print(f"  ⛔ Filtered out {filtered_count} tracks (liked + disliked + recently recommended)")

    if not all_recommendations:
        print("No recommendations found")
        return []

    # 3. Score and rank recommendations
    print("\nStep 3: Scoring and ranking...")

    # Get liked artists for boosting
    liked_artists = set()
    if user_id:
        liked_tracks_data = db.get_liked_tracks(user_id)
        for liked in liked_tracks_data:
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

        # Prefer earlier batches slightly (more relevant to original seeds)
        batch_penalty = rec['batch'] * 0.02
        score -= batch_penalty

        # Add randomization for diversity (±10%)
        random_factor = random.uniform(-0.1, 0.1)
        score += random_factor

        rec['score'] = score

    # Sort by score
    all_recommendations.sort(key=lambda x: x['score'], reverse=True)

    # 4. Apply diversity filter
    print("\nStep 4: Applying diversity filters...")
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
            'source': 'ReccoBeats API'
        })

        if artist_id:
            artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1

        if len(final_recommendations) >= limit:
            break

    print(f"\n✓ Generated {len(final_recommendations)} diverse recommendations via ReccoBeats")
    return final_recommendations
