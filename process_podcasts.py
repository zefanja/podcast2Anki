#!/usr/bin/python3

import os
import json
import requests
from faster_whisper import WhisperModel

# Directories for downloads and transcripts
EPISODE_DIR = "episodes"
TRANSCRIPT_DIR = "transcripts"
RESULTS_DIR = "results"

def ensure_directories():
    """
    Ensures the necessary directories for episodes and transcripts exist.
    """
    os.makedirs(EPISODE_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

def load_episodes(filename="detailed_episodes.json"):
    """
    Loads the JSON file containing episode details.
    """
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)

def save_episodes(data, filename="detailed_episodes.json"):
    """
    Saves the updated episode details to the JSON file.
    """
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def download_episode(url, episode_id):
    """
    Downloads an episode if not already downloaded.
    Returns the local file path of the downloaded episode.
    """
    local_path = os.path.join(EPISODE_DIR, f"{episode_id}.mp3")
    if os.path.exists(local_path):
        print(f"Episode {episode_id} already downloaded.")
        return local_path
    
    print(f"Downloading episode {episode_id}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(local_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    
    print(f"Episode {episode_id} downloaded to {local_path}.")
    return local_path

def transcribe_episode(file_path, episode_id, model):
    """
    Transcribes an episode using faster-whisper.
    Returns the local path of the transcript file.
    """
    transcript_path = os.path.join(TRANSCRIPT_DIR, f"{episode_id}.txt")
    if os.path.exists(transcript_path):
        print(f"Transcript for episode {episode_id} already exists.")
        return transcript_path
    
    print(f"Transcribing episode {episode_id}...")
    segments, _ = model.transcribe(file_path)
    
    with open(transcript_path, "w", encoding="utf-8") as file:
        for segment in segments:
            file.write(f"{segment.text}\n")
    
    print(f"Transcript for episode {episode_id} saved to {transcript_path}.")
    return transcript_path

def process_episodes(filename="detailed_episodes.json"):
    """
    Processes episodes: downloads, transcribes, and updates the JSON file.
    """
    ensure_directories()
    model = WhisperModel("small", device="cpu")  # Adjust model and device as needed
    
    episodes = load_episodes(filename)
    for episode in episodes:
        if "transcript_file" in episode and os.path.exists(episode["transcript_file"]):
            print(f"Episode {episode['episode_id']} already processed.")
            continue
        
        episode_file = download_episode(episode["episode_url"], episode["episode_id"])
        transcript_file = transcribe_episode(episode_file, episode["episode_id"], model)
        episode["transcript_file"] = transcript_file
    
    save_episodes(episodes, filename)

if __name__ == "__main__":
    process_episodes()
