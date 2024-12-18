import os
import os.path as op
import json
import random
from ytmusicapi import YTMusic
from time import sleep
from tqdm import tqdm

yt = YTMusic("browser.json")

# Set to use an existing playlist as the source of tracks to recommend from.
# Otherwise use liked songs.
SOURCE_PLAYLIST_ID = None

# Playlist you want to add to.
DESTINATION_PLAYLIST_ID ='PLXYeZ3VwLuLuZpwfs3GQQFvOuo7sg8IzF'

# Max views of a song in liked songs to avoid things too popular.
MAX_VIEWS = 100_000

# Set to None ot avoid limit
MAX_NEW_TRACKS = 90

CACHE_HISTORY = './cache/history.json'
CACHE_RADIO = './cache/recommended.json'
CACHE_SEEDED_TRACKS = './cache/seeded_tracks.json'

os.makedirs(op.dirname(CACHE_HISTORY), exist_ok=True)

def get_playlist_tracks(playlistId):
    playlist = yt.get_playlist(playlistId)
    return playlist['tracks']

def add_metadata_to_tracks(tracks):
    results=[]
    for track in tqdm(tracks):
        results.append(yt.get_song(track['videoId']))
        sleep(0.3)
    return results

def get_liked_tracks():
    liked_tracks = yt.get_liked_songs()['tracks']

    # Drop any liked_tracks that are already in the cache for being used as recommended.
    if op.exists(CACHE_SEEDED_TRACKS):
        with open(CACHE_SEEDED_TRACKS, 'r') as f:
            seeded_tracks = json.load(f)
            seeded_ids = set([track['videoId'] for track in seeded_tracks])
        liked_tracks = [track for track in liked_tracks if track['videoId'] not in seeded_ids]

    # downsample before pulling metadata
    liked_tracks = random.sample(liked_tracks, min(int(MAX_NEW_TRACKS*1.5), len(liked_tracks)))

    return add_metadata_to_tracks(liked_tracks)


def get_recommended_tracks(seed_tracks):
    """Returns just 'videoDetails' portion of json ot avoid bloat."""
    new_songs = []
    for track in tqdm(seed_tracks):
        # print(track)
        new_songs.extend(yt.get_watch_playlist(videoId=track['videoId'],
                                               limit=3, 
                                               radio = True)['tracks'])
        sleep(0.3)

    # downsample before pulling metadata
    new_songs = random.sample(new_songs, min(int(MAX_NEW_TRACKS*1.5), len(new_songs)))

    recommended_metadata= add_metadata_to_tracks(new_songs)

    recommended_metadata = [track['videoDetails'] for track in recommended_metadata]

    # write list
    with open(CACHE_RADIO, 'w') as f:
        json.dump(recommended_metadata, f, indent=2)

    return recommended_metadata

def get_history_tracks():
    current_history = []
    if op.exists(CACHE_HISTORY):
        # read json file to current_history
        with open(CACHE_HISTORY, 'r') as f:
            current_history = json.load(f)

    new_history = yt.get_history()

    combined_history = current_history + new_history

    # Drop duplicates based on track['videoId']
    keep_history = []
    seen = set()
    for track in combined_history:
        if track['videoId'] not in seen:
            seen.add(track['videoId'])
            keep_history.append(track)
    

    with open(CACHE_HISTORY, 'w') as f:
        json.dump(keep_history, f, indent=2)

    return keep_history

def add_tracks_to_playlist(new_tracks, playlistId):
    print(f"{len(new_tracks)} candidate new tracks to playlist")
    # Add new tracks to playlist
    current_playlist_tracks = get_playlist_tracks(playlistId)
    history_tracks = get_history_tracks()

    # Drop any new tracks if author is already in the playlist or history
    print('current_playlist_tracks', current_playlist_tracks[0])
    set_exclude_authors = set([track['artists'][0]['name'] for track in current_playlist_tracks+history_tracks])
    # set_exclude_authors = set_exclude_authors.union(set([track['artists']['name'] for track in history_tracks]))
    new_tracks = [track for track in new_tracks if track['author'] not in set_exclude_authors]
    print(f"{len(new_tracks)} candidate new tracks to playlist after dropping known authors")

    set_exclude_videoIds = set([track['videoId'] for track in current_playlist_tracks + history_tracks])

    if len(new_tracks) == 0:
        print("No new tracks to add to playlist")
        return
    # drop any from new_tracks that are already in the playlist or history
    print(f"{len(new_tracks)} candidate new tracks to playlist")
    new_track_ids = [track['videoId'] for track in new_tracks if track['videoId'] not in set_exclude_videoIds]
    print(f"{len(new_tracks)} actual new tracks to playlist")

    # if max new tracks is not none choose random set
    if MAX_NEW_TRACKS:
        new_track_ids = random.sample(new_track_ids, min(MAX_NEW_TRACKS, len(new_track_ids)))   

    for batch in tqdm(range(0,len(new_track_ids),5)):
        print(f'adding batch {batch} to {batch+5} to playlist')
        yt.add_playlist_items(playlistId=playlistId, videoIds=new_track_ids[batch:batch+5], )
        sleep(1.3)



def cleanup_playlist(playlistId = DESTINATION_PLAYLIST_ID):
    # Remove any songs in playlist that are in history.
    current_playlist_tracks = get_playlist_tracks(playlistId)
    history_tracks = get_history_tracks()
    removeable = [track for track in current_playlist_tracks if track['videoId'] in [track['videoId'] for track in history_tracks]]
    print(f"Removing {len(removeable)} tracks from playlist")
    if len(removeable) > 0:
        yt.remove_playlist_items(playlistId=playlistId, videos=removeable, )


def find_and_add_new_tracks_to_playlist():
    print("Get seed tracks")
    if SOURCE_PLAYLIST_ID:
        seed_tracks = get_playlist_tracks(SOURCE_PLAYLIST_ID)
    else:
        seed_tracks = get_liked_tracks()
        
        # Filter liked_tracks to rarer ones:
        seed_tracks = [track['videoDetails'] for track in seed_tracks]
        # seed_tracks = [track['videoDetails'] for track in seed_tracks if int(track.get('videoDetails',{}).get('viewCount',0)) < MAX_VIEWS]
        if MAX_NEW_TRACKS:
            # Cut seed tracks in half since we get multiple suggestions per seed.
            seed_tracks = random.sample(seed_tracks, min(int(MAX_NEW_TRACKS/2), len(seed_tracks)))
        
    print("Seed tracks", len(seed_tracks))

    # Update cache of seeded tracks.
    if op.exists(CACHE_SEEDED_TRACKS):
        with open(CACHE_SEEDED_TRACKS, 'r') as f:
            seeded_tracks = json.load(f)
    else:
        seeded_tracks = []

    # write list
    with open(CACHE_SEEDED_TRACKS, 'w') as f:
        new_seeded_tracks = seeded_tracks + seed_tracks
        json.dump(new_seeded_tracks, f, indent=2)

    print("Get recommendations")
    new_track_details = get_recommended_tracks(seed_tracks)
    # Filter new_tracks to rarer ones
    new_track_details = [track for track in new_track_details if int(track['viewCount']) < MAX_VIEWS]

    add_tracks_to_playlist(new_track_details, DESTINATION_PLAYLIST_ID)

if __name__=='__main__':
    find_and_add_new_tracks_to_playlist()
    cleanup_playlist(DESTINATION_PLAYLIST_ID)