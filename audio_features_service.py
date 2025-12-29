"""
Audio Features Service using RapidAPI Track Analysis
Workaround for Spotify's deprecated audio features endpoint for new apps.
"""

import os
import requests
from typing import Dict, Optional, List
from dotenv import load_dotenv
import time

load_dotenv()


class AudioFeaturesService:
    """Service for fetching Spotify audio features via RapidAPI."""

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

    def get_audio_features(self, track_id: str) -> Optional[Dict]:
        """
        Get audio features for a single track.

        Args:
            track_id: Spotify track ID

        Returns:
            Dictionary with audio features or None if error
        """
        try:
            url = f"{self.base_url}/{track_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
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
            print(f"HTTP error fetching audio features for track {track_id}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching audio features for track {track_id}: {e}")
            return None

    def get_audio_features_batch(self, track_ids: List[str], rate_limit_delay: float = 0.2) -> Dict[str, Dict]:
        """
        Get audio features for multiple tracks with rate limiting.

        Args:
            track_ids: List of Spotify track IDs
            rate_limit_delay: Delay between requests in seconds (default 0.2s = 5 req/sec)

        Returns:
            Dictionary mapping track_id to audio features
        """
        results = {}

        print(f"Fetching audio features for {len(track_ids)} tracks...")

        for i, track_id in enumerate(track_ids):
            if i > 0 and i % 10 == 0:
                print(f"Progress: {i}/{len(track_ids)} tracks processed")

            features = self.get_audio_features(track_id)

            if features:
                results[track_id] = features

            # Rate limiting to avoid hitting API limits
            if i < len(track_ids) - 1:
                time.sleep(rate_limit_delay)

        print(f"Successfully fetched features for {len(results)}/{len(track_ids)} tracks")
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
