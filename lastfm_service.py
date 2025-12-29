"""
Last.fm API service for music recommendations.
Provides functions to get similar tracks and artists using the Last.fm API.
"""

import os
import pylast
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class LastFMService:
    """Service class for interacting with Last.fm API."""

    def __init__(self):
        """Initialize Last.fm network connection."""
        self.api_key = os.getenv('LASTFM_API_KEY')
        self.api_secret = os.getenv('LASTFM_API_SECRET')

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Last.fm API credentials not found. "
                "Please set LASTFM_API_KEY and LASTFM_API_SECRET in .env file"
            )

        self.network = pylast.LastFMNetwork(
            api_key=self.api_key,
            api_secret=self.api_secret
        )

    def get_similar_artists(self, artist_name: str, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get similar artists to the given artist.

        Args:
            artist_name: Name of the artist
            limit: Maximum number of similar artists to return

        Returns:
            List of dictionaries with artist information and similarity score
        """
        try:
            artist = self.network.get_artist(artist_name)
            similar = artist.get_similar(limit=limit)

            results = []
            for item in similar:
                results.append({
                    'name': item.item.name,
                    'match_score': float(item.match),  # Similarity score (0-1)
                    'url': item.item.get_url()
                })

            return results
        except pylast.WSError as e:
            print(f"Last.fm API error for artist '{artist_name}': {e}")
            return []
        except Exception as e:
            print(f"Error getting similar artists for '{artist_name}': {e}")
            return []

    def get_similar_tracks(self, track_name: str, artist_name: str, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get similar tracks to the given track.

        Args:
            track_name: Name of the track
            artist_name: Name of the artist
            limit: Maximum number of similar tracks to return

        Returns:
            List of dictionaries with track information and similarity score
        """
        try:
            track = self.network.get_track(artist_name, track_name)
            similar = track.get_similar(limit=limit)

            results = []
            for item in similar:
                track_obj = item.item
                results.append({
                    'name': track_obj.title,
                    'artist': track_obj.artist.name,
                    'match_score': float(item.match),  # Similarity score (0-1)
                    'url': track_obj.get_url()
                })

            return results
        except pylast.WSError as e:
            print(f"Last.fm API error for track '{track_name}' by '{artist_name}': {e}")
            return []
        except Exception as e:
            print(f"Error getting similar tracks for '{track_name}': {e}")
            return []

    def get_artist_top_tracks(self, artist_name: str, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get top tracks for an artist.

        Args:
            artist_name: Name of the artist
            limit: Maximum number of top tracks to return

        Returns:
            List of dictionaries with track information
        """
        try:
            artist = self.network.get_artist(artist_name)
            top_tracks = artist.get_top_tracks(limit=limit)

            results = []
            for item in top_tracks:
                track_obj = item.item
                results.append({
                    'name': track_obj.title,
                    'artist': artist_name,
                    'playcount': int(item.weight) if item.weight else 0,
                    'url': track_obj.get_url()
                })

            return results
        except pylast.WSError as e:
            print(f"Last.fm API error for artist '{artist_name}': {e}")
            return []
        except Exception as e:
            print(f"Error getting top tracks for artist '{artist_name}': {e}")
            return []

    def search_track_on_spotify(self, track_name: str, artist_name: str, sp) -> Optional[str]:
        """
        Search for a track on Spotify to get its Spotify ID.

        Args:
            track_name: Name of the track
            artist_name: Name of the artist
            sp: Spotipy client instance

        Returns:
            Spotify track ID or None if not found
        """
        try:
            query = f"track:{track_name} artist:{artist_name}"
            results = sp.search(q=query, type='track', limit=1)

            if results['tracks']['items']:
                return results['tracks']['items'][0]['id']
            return None
        except Exception as e:
            print(f"Error searching Spotify for '{track_name}' by '{artist_name}': {e}")
            return None


# Create a singleton instance
_lastfm_service = None


def get_lastfm_service() -> LastFMService:
    """Get or create the Last.fm service instance."""
    global _lastfm_service
    if _lastfm_service is None:
        _lastfm_service = LastFMService()
    return _lastfm_service
