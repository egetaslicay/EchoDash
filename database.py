"""
Database module for EchoDash - SQLite persistence layer
Tracks user listening history and recommendations over time.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os


DB_PATH = 'echodash.db'


def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_db():
    """Initialize the database with tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spotify_id TEXT UNIQUE NOT NULL,
            display_name TEXT,
            email TEXT,
            profile_image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Listening snapshots table - stores user's top tracks/artists at a point in time
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listening_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_range TEXT NOT NULL,
            top_tracks TEXT NOT NULL,
            top_artists TEXT NOT NULL,
            audio_features TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Recommendations history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            track_id TEXT NOT NULL,
            track_name TEXT,
            artist_name TEXT,
            score REAL,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # User feedback table - likes and dislikes for tracks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            track_id TEXT NOT NULL,
            track_name TEXT,
            artist_name TEXT,
            feedback INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, track_id)
        )
    ''')

    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_spotify ON users(spotify_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_user ON listening_snapshots(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_time ON listening_snapshots(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_recs_user ON recommendations(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_user ON user_feedback(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_track ON user_feedback(track_id)')

    conn.commit()
    conn.close()
    print("✓ Database initialized successfully")


def get_or_create_user(spotify_id: str, display_name: str = None,
                       email: str = None, profile_image: str = None) -> int:
    """
    Get existing user or create new one.
    Returns user_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Try to find existing user
    cursor.execute('SELECT id FROM users WHERE spotify_id = ?', (spotify_id,))
    result = cursor.fetchone()

    if result:
        user_id = result['id']
        # Update last login
        cursor.execute('''
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP,
                display_name = COALESCE(?, display_name),
                email = COALESCE(?, email),
                profile_image = COALESCE(?, profile_image)
            WHERE id = ?
        ''', (display_name, email, profile_image, user_id))
    else:
        # Create new user
        cursor.execute('''
            INSERT INTO users (spotify_id, display_name, email, profile_image)
            VALUES (?, ?, ?, ?)
        ''', (spotify_id, display_name, email, profile_image))
        user_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return user_id


def save_listening_snapshot(user_id: int, time_range: str,
                           top_tracks: List[Dict], top_artists: List[Dict],
                           audio_features: Dict = None):
    """
    Save a snapshot of user's listening data.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Convert lists to JSON for storage
    tracks_json = json.dumps(top_tracks)
    artists_json = json.dumps(top_artists)
    features_json = json.dumps(audio_features) if audio_features else None

    cursor.execute('''
        INSERT INTO listening_snapshots
        (user_id, time_range, top_tracks, top_artists, audio_features)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, time_range, tracks_json, artists_json, features_json))

    conn.commit()
    conn.close()


def save_recommendations(user_id: int, recommendations: List[Dict]):
    """
    Save user's recommendations to history.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    for rec in recommendations:
        cursor.execute('''
            INSERT INTO recommendations
            (user_id, track_id, track_name, artist_name, score, source)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            rec.get('id'),
            rec.get('name'),
            rec.get('artist'),
            rec.get('score'),
            rec.get('source')
        ))

    conn.commit()
    conn.close()


def get_user_snapshots(user_id: int, limit: int = 10) -> List[Dict]:
    """
    Get user's listening snapshots, most recent first.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, timestamp, time_range, top_tracks, top_artists, audio_features
        FROM listening_snapshots
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (user_id, limit))

    rows = cursor.fetchall()
    conn.close()

    snapshots = []
    for row in rows:
        snapshots.append({
            'id': row['id'],
            'timestamp': row['timestamp'],
            'time_range': row['time_range'],
            'top_tracks': json.loads(row['top_tracks']),
            'top_artists': json.loads(row['top_artists']),
            'audio_features': json.loads(row['audio_features']) if row['audio_features'] else None
        })

    return snapshots


def get_user_recommendations_history(user_id: int, limit: int = 50) -> List[Dict]:
    """
    Get user's recommendation history.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT track_id, track_name, artist_name, score, source, created_at
        FROM recommendations
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (user_id, limit))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_user_stats(user_id: int) -> Dict:
    """
    Get aggregate statistics for a user.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get snapshot count
    cursor.execute('SELECT COUNT(*) as count FROM listening_snapshots WHERE user_id = ?', (user_id,))
    snapshot_count = cursor.fetchone()['count']

    # Get recommendation count
    cursor.execute('SELECT COUNT(*) as count FROM recommendations WHERE user_id = ?', (user_id,))
    rec_count = cursor.fetchone()['count']

    # Get first snapshot date
    cursor.execute('''
        SELECT MIN(timestamp) as first_snapshot
        FROM listening_snapshots
        WHERE user_id = ?
    ''', (user_id,))
    first_snapshot = cursor.fetchone()['first_snapshot']

    conn.close()

    return {
        'snapshots_count': snapshot_count,
        'recommendations_count': rec_count,
        'first_snapshot': first_snapshot,
        'has_history': snapshot_count > 0
    }


def save_feedback(user_id: int, track_id: str, track_name: str, artist_name: str, feedback: int):
    """
    Save user feedback (like/dislike) for a track.

    Args:
        user_id: Database user ID
        track_id: Spotify track ID
        track_name: Track name
        artist_name: Artist name
        feedback: 1 for like, -1 for dislike
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO user_feedback
            (user_id, track_id, track_name, artist_name, feedback, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, track_id, track_name, artist_name, feedback))

        conn.commit()
    except Exception as e:
        print(f"Error saving feedback: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_user_feedback(user_id: int) -> Dict[str, int]:
    """
    Get all feedback for a user as a dict of track_id -> feedback.

    Args:
        user_id: Database user ID

    Returns:
        Dictionary mapping track IDs to feedback values (1 or -1)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT track_id, feedback
        FROM user_feedback
        WHERE user_id = ?
    ''', (user_id,))

    feedback_dict = {row['track_id']: row['feedback'] for row in cursor.fetchall()}

    conn.close()
    return feedback_dict


def get_liked_tracks(user_id: int) -> List[Dict]:
    """Get all tracks the user liked."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT track_id, track_name, artist_name, created_at
        FROM user_feedback
        WHERE user_id = ? AND feedback = 1
        ORDER BY created_at DESC
    ''', (user_id,))

    liked = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return liked


def get_disliked_tracks(user_id: int) -> List[Dict]:
    """Get all tracks the user disliked."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT track_id, track_name, artist_name, created_at
        FROM user_feedback
        WHERE user_id = ? AND feedback = -1
        ORDER BY created_at DESC
    ''', (user_id,))

    disliked = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return disliked


def delete_feedback(user_id: int, track_id: str):
    """Delete feedback for a specific track."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        DELETE FROM user_feedback
        WHERE user_id = ? AND track_id = ?
    ''', (user_id, track_id))

    conn.commit()
    conn.close()


# Initialize database on module import
if not os.path.exists(DB_PATH):
    init_db()
