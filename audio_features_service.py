"""
Audio Features Service using RapidAPI Track Analysis
Workaround for Spotify's deprecated audio features endpoint for new apps.
Includes intelligent rate limiting and retry logic.
"""

import os
import requests
from typing import Dict, Optional, List
from dotenv import load_dotenv
import time

load_dotenv()


class AudioFeaturesService:
    """Service for fetching Spotify audio features via RapidAPI with smart rate limiting."""

    def __init__(self):
        """Initialize RapidAPI audio features service."""
        self.api_key = os.getenv('RAPID_API_KEY')

        if not self.api_key:
            raise ValueError(
                "RapidAPI key not found. "
                "Please set RAPID_API_KEY in .env file. "
                "Get your key from: https://rapidapi.com/Glavier/api/track-analysis"
            )

        self.headers = {
            'x-rapidapi-host': 'track-analysis.p.rapidapi.com',
            'x-rapidapi-key': self.api_key
        }
        self.base_url = 'https://track-analysis.p.rapidapi.com/pktx/spotify'

        # Rate limiting settings
        self.max_retries = 3
        self.base_retry_delay = 2  # seconds

    def get_audio_features(self, track_id: str, retry_count: int = 0) -> Optional[Dict]:
        """
        Get audio features for a single track with retry logic.

        Args:
            track_id: Spotify track ID
            retry_count: Current retry attempt number

        Returns:
            Dictionary with audio features or None if error
        """
        try:
            url = f"{self.base_url}/{track_id}"
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            data = response.json()

            # Extract and normalize features
            features = {
                'track_id': track_id,
                'acousticness': float(data.get('acousticness', 0)),
                'danceability': float(data.get('danceability', 0)),
                'energy': float(data.get('energy', 0)),
                'instrumentalness': float(data.get('instrumentalness', 0)),
                'loudness': self._parse_loudness(data.get('loudness', '0 dB')),
                'tempo': float(data.get('tempo', 0)),
                'speechiness': float(data.get('speechiness', 0)),
                'valence': float(data.get('valence', 0))  # Musical positivity
            }

            return features

        except requests.exceptions.HTTPError as e:
            # Handle rate limiting (429) and forbidden (403) errors with retry
            if e.response.status_code in [429, 403]:
                if retry_count < self.max_retries:
                    # Exponential backoff: 2s, 4s, 8s
                    retry_delay = self.base_retry_delay * (2 ** retry_count)
                    print(f"Rate limited for track {track_id}. Retrying in {retry_delay}s... (attempt {retry_count + 1}/{self.max_retries})")
                    time.sleep(retry_delay)
                    return self.get_audio_features(track_id, retry_count + 1)
                else:
                    print(f"Max retries reached for track {track_id} after rate limiting")
                    return None
            else:
                print(f"HTTP {e.response.status_code} error for track {track_id}")
                return None

        except requests.exceptions.Timeout:
            if retry_count < self.max_retries:
                print(f"Timeout for track {track_id}. Retrying...")
                time.sleep(1)
                return self.get_audio_features(track_id, retry_count + 1)
            return None

        except Exception as e:
            print(f"Error fetching audio features for track {track_id}: {e}")
            return None

    def get_audio_features_batch(self, track_ids: List[str], rate_limit_delay: float = 0.6) -> Dict[str, Dict]:
        """
        Get audio features for multiple tracks with conservative rate limiting.

        Args:
            track_ids: List of Spotify track IDs
            rate_limit_delay: Delay between requests in seconds (default 0.6s ≈ 1.67 req/sec)

        Returns:
            Dictionary mapping track_id to audio features
        """
        results = {}
        failed_count = 0

        print(f"Fetching audio features for {len(track_ids)} tracks (rate limited to ~1.67 req/sec)...")

        for i, track_id in enumerate(track_ids):
            if i > 0 and i % 5 == 0:
                print(f"Progress: {i}/{len(track_ids)} tracks processed ({len(results)} successful, {failed_count} failed)")

            features = self.get_audio_features(track_id)

            if features:
                results[track_id] = features
            else:
                failed_count += 1

            # Rate limiting to avoid hitting API limits (conservative 0.6s = ~1.67 req/sec)
            if i < len(track_ids) - 1:
                time.sleep(rate_limit_delay)

        success_rate = (len(results) / len(track_ids) * 100) if track_ids else 0
        print(f"Successfully fetched features for {len(results)}/{len(track_ids)} tracks ({success_rate:.1f}% success rate)")
        return results

    @staticmethod
    def _parse_loudness(loudness_str) -> float:
        """Parse loudness string like '-5.123 dB' to float."""
        try:
            if isinstance(loudness_str, (int, float)):
                return float(loudness_str)
            return float(str(loudness_str).replace('dB', '').strip())
        except:
            return 0.0


# Singleton instance
_audio_features_service = None


def get_audio_features_service() -> AudioFeaturesService:
    """Get or create the audio features service instance."""
    global _audio_features_service
    if _audio_features_service is None:
        _audio_features_service = AudioFeaturesService()
    return _audio_features_service
