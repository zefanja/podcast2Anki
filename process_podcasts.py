#!/usr/bin/python3

import os
import json
import requests
from pydub import AudioSegment
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Directories for downloads and transcripts
EPISODE_DIR = "episodes"
TRANSCRIPT_DIR = "transcripts"
RESULTS_DIR = "results"
DETAILED_EPISODES_FILE = f"{RESULTS_DIR}/detailed_episodes.json"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def ensure_directories():
    os.makedirs(EPISODE_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

def load_episodes(filename="detailed_episodes.json"):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)

def save_episodes(data, filename="detailed_episodes.json"):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def download_episode(url, episode_id):
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

def split_audio(file_path):
    audio = AudioSegment.from_file(file_path)
    chunks = []
    max_chunk_size = 20 * 60 * 1000  # 20 minutes in milliseconds

    for i in range(0, len(audio), max_chunk_size):
        chunks.append(audio[i:i + max_chunk_size])

    return chunks

def transcribe_chunk(chunk, chunk_id):
    client = OpenAI(api_key=OPENAI_API_KEY)
    chunk.export(f"{chunk_id}.mp3", format="mp3")
    with open(f"{chunk_id}.mp3", "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )
    os.remove(f"{chunk_id}.mp3")
    return response

def transcribe_episode(file_path, episode_id):
    transcript_path = os.path.join(TRANSCRIPT_DIR, f"{episode_id}.txt")
    if os.path.exists(transcript_path):
        print(f"Transcript for episode {episode_id} already exists.")
        return transcript_path

    print(f"Transcribing episode {episode_id}...")
    chunks = split_audio(file_path)
    transcripts = [transcribe_chunk(chunk, f"{episode_id}_chunk_{i}") for i, chunk in enumerate(chunks)]
    full_transcript = "\n".join(transcripts)

    with open(transcript_path, "w", encoding="utf-8") as file:
        file.write(full_transcript)

    print(f"Transcript for episode {episode_id} saved to {transcript_path}.")
    return transcript_path

def process_episodes(filename=DETAILED_EPISODES_FILE):
    """
    Processes episodes: transcribes and updates the JSON file if no transcript exists.
    Downloads audio only if a transcript does not already exist.
    """
    ensure_directories()
    #model = WhisperModel(WHISPER_MODEL, device="cpu")  # Adjust model and device as needed

    episodes = load_episodes(filename)
    for episode in episodes:
        episode_id = episode['episode_id'].replace("/","_")
        transcript_path = os.path.join(TRANSCRIPT_DIR, f"{episode_id}.txt")

        if os.path.exists(transcript_path):
            print(f"Transcript for episode {episode_id} already exists. Skipping download.")
            continue
        
        episode_file = download_episode(episode["episode_url"], episode_id)
        transcript_file = transcribe_episode(episode_file, episode_id)
        episode["transcript_file"] = transcript_file
    
    save_episodes(episodes, filename)

if __name__ == "__main__":
    process_episodes()

