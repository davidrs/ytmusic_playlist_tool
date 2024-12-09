import os
import os.path as op
import json
import random
from ytmusicapi import YTMusic
from time import sleep


yt = YTMusic("browser.json")

# Set to use an existing playlist as the source of tracks to recommend from.
# Otherwise use liked songs.
SOURCE_PLAYLIST_ID = None

# Playlist you want to add to.
DESTINATION_PLAYLIST_ID ='PLXYeZ3VwLuLuZpwfs3GQQFvOuo7sg8IzF'

# Max views of a song in liked songs to avoid things too popular.
MAX_VIEWS = 100_000

# Set to None ot avoid limit
MAX_NEW_TRACKS = 20

CACHE_HISTORY = './cache/history.json'
CACHE_RADIO = './cache/recommended.json'

os.makedirs(op.dirname(CACHE_HISTORY), exist_ok=True)

def get_playlist_tracks(playlistId):
    playlist = yt.get_playlist(playlistId)
    return playlist['tracks']

def add_metadata_to_tracks(tracks):
    results=[]
    for track in tracks:
        results.append(yt.get_song(track['videoId']))
        sleep(0.3)
    return results

def get_liked_tracks():
    liked_tracks = yt.get_liked_songs()['tracks']
    return add_metadata_to_tracks(liked_tracks)


def get_recommended_tracks(seed_tracks):
    new_songs = []
    for track in seed_tracks:
        # print(track)
        new_songs.extend(yt.get_watch_playlist(videoId=track['videoId'],
                                               limit=3, 
                                               radio = True)['tracks'])
        sleep(0.3)

    recommended_metadata= add_metadata_to_tracks(new_songs)

    # write list
    with open(CACHE_RADIO, 'w') as f:
        json.dump(recommended_metadata, f)

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
        json.dump(keep_history, f)

    return keep_history

def add_tracks_to_playlist(new_tracks, playlistId):
    # Add new tracks to playlist
    current_playlist_tracks = get_playlist_tracks(playlistId)
    history_tracks = get_history_tracks()
    set_exclude_videoIds = set([track['videoId'] for track in current_playlist_tracks + history_tracks])

    # drop any from new_tracks that are already in the playlist or history
    print(f"{len(new_tracks)} candidate new tracks to playlist")
    new_track_ids = [track['videoId'] for track in new_tracks if track['videoId'] not in set_exclude_videoIds]
    print(f"{len(new_tracks)} actual new tracks to playlist")

    # if max new tracks is not none choose random set
    if MAX_NEW_TRACKS:
        new_track_ids = random.sample(new_track_ids, min(MAX_NEW_TRACKS, len(new_track_ids)))   

    for batch in range(0,len(new_track_ids),5):
        print(f'adding batch {batch} to {batch+5} to playlist')
        yt.add_playlist_items(playlistId=playlistId, videoIds=new_track_ids[batch:batch+5], )
        sleep(1.3)



def cleanup_playlist(playlistId):
    # Remove any songs in playlist that are in history.
    current_playlist_tracks = get_playlist_tracks(DESTINATION_PLAYLIST_ID)
    history_tracks = get_history_tracks()
    removeable = [track for track in current_playlist_tracks if track['videoId'] in [track['videoId'] for track in history_tracks]]
    print(f"Removing {len(removeable)} tracks from playlist")
    yt.remove_playlist_items(playlistId=DESTINATION_PLAYLIST_ID, videos=removeable, )


def find_and_add_new_tracks_to_playlist():
    if SOURCE_PLAYLIST_ID:
        seed_tracks = get_playlist_tracks(SOURCE_PLAYLIST_ID)
    else:
        seed_tracks = get_liked_tracks()
        
        # Filter liked_tracks to rarer ones:
        print(seed_tracks[0].get('videoDetails',{}))
        seed_tracks = [track['videoDetails'] for track in seed_tracks]
        # seed_tracks = [track['videoDetails'] for track in seed_tracks if int(track.get('videoDetails',{}).get('viewCount',0)) < MAX_VIEWS]
        if MAX_NEW_TRACKS:
            # Cut seed tracks in half since we get multiple suggestions per seed.
            seed_tracks = random.sample(seed_tracks, min(int(MAX_NEW_TRACKS/2), len(seed_tracks)))
        sleep(0.3)
    print("Get recommendations", seed_tracks[:2])
    new_tracks = get_recommended_tracks(seed_tracks)
    # Filter new_tracks to rarer ones
    new_tracks = [track['videoDetails'] for track in new_tracks if int(track['videoDetails']['viewCount']) < MAX_VIEWS]

    add_tracks_to_playlist(new_tracks, DESTINATION_PLAYLIST_ID)

if __name__=='__main__':
    find_and_add_new_tracks_to_playlist()
    cleanup_playlist(DESTINATION_PLAYLIST_ID)