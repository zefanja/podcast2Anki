#!/usr/bin/python3

import requests
from requests.auth import HTTPBasicAuth
import feedparser
import json
import argparse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os


# Configuration
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

RESULTS_DIR = "results"
DETAILED_EPISODES_FILE = f"{RESULTS_DIR}/detailed_episodes.json"
TIMESTAMP_FILE = f"{RESULTS_DIR}/last_timestamp.txt"


# Cache for podcast details
podcast_cache = {}

def get_last_timestamp():
    """Reads the last saved timestamp from the file."""
    try:
        with open(TIMESTAMP_FILE, "r") as file:
            return int(file.read().strip())
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading timestamp file: {e}")
        return None

def save_last_timestamp(timestamp):
    """Saves the timestamp to a file."""
    try:
        with open(TIMESTAMP_FILE, "w") as file:
            file.write(str(timestamp))
    except Exception as e:
        print(f"Error saving timestamp: {e}")

def get_episode_actions(since=None, podcast=None, device=None, aggregated=False):
    """
    Fetches episode actions for the user, filtered by optional parameters.
    """
    endpoint = f"{API_BASE_URL}episodes/{USERNAME}.json"
    params = {}
    if since is not None:
        params["since"] = since
    if podcast is not None:
        params["podcast"] = podcast
    if device is not None:
        params["device"] = device
    if aggregated:
        params["aggregated"] = "true"

    response = requests.get(endpoint, auth=HTTPBasicAuth(USERNAME, PASSWORD), params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch episode actions: {response.status_code} {response.text}")
    
    data = response.json()
    # Save the last timestamp from the response
    if "timestamp" in data:
        save_last_timestamp(data["timestamp"])
    return data

def fetch_episode_details(podcast_url, episode_id):
    """
    Fetches the specific episode from the podcast feed and returns its title and author.
    Only retrieves the episode entry that matches the episode URL.
    """
    if podcast_url in podcast_cache:
        feed = podcast_cache[podcast_url]
    else:
        feed = feedparser.parse(podcast_url)
        if feed.bozo:  # Check for parsing errors
            raise Exception(f"Failed to parse podcast feed: {podcast_url}")

    podcast_title = feed.feed.get("title", "Unknown Podcast")

    # Find the episode that matches the episode URL
    for entry in feed.entries:
        if entry.id == episode_id:
            episode_title = entry.get("title", "Unknown Episode")
            episode_author = entry.get("author", entry.get("itunes_author", "Unknown Author"))

            if podcast_url not in podcast_cache:
                podcast_cache[podcast_url] = feed

            print(episode_title, episode_author)
            return episode_title, episode_author, podcast_title

    raise Exception(f"Episode not found in the feed: {episode_url}")

def get_fully_listened_episodes_with_details(since=None):
    """
    Fetches fully listened episodes with additional details from the podcast feed.
    """
    actions_response = get_episode_actions(since=since)
    actions = actions_response.get("actions", [])
    # Filter for 'play' actions where position equals total
    fully_listened_episodes = [
        action for action in actions
        if action.get("action") == "play" and action.get("position") == action.get("total")
    ]

    # Enhance each episode with podcast and author details
    detailed_episodes = []
    for episode in fully_listened_episodes:
        podcast_url = episode.get("podcast")
        episode_url = episode.get("episode")
        episode_id = episode.get("guid")
        episode_title = episode.get("episode_title", "Unknown Episode")
        date_string = episode.get("timestamp")

        # Parse the string to a timezone-aware datetime object
        utc_dt = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

        # Convert to UTC+7
        date = utc_dt + timedelta(hours=7)
        # Format the output as DD.MM.YYYY HH:MM
        date_formatted = date.strftime("%d.%m.%Y %H:%M")

        # get Podcast details
        if podcast_url and episode_url:
            try:
                episode_title, episode_author, podcast_title = fetch_episode_details(podcast_url, episode_id)
                detailed_episodes.append({
                    "podcast_title": podcast_title,
                    "podcast_author": episode_author,
                    "episode_title": episode_title,
                    "episode_id": episode_id,
                    "episode_url": episode_url,
                    "date": date_formatted
                })
            except Exception as e:
                print(f"Error fetching details for episode {episode_url}: {e}")
    return detailed_episodes

def save_episodes_to_json(detailed_episodes, filename=DETAILED_EPISODES_FILE):
    """
    Saves the list of detailed episodes to a JSON file.
    """
    try:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(detailed_episodes, file, ensure_ascii=False, indent=4)
        print(f"Successfully saved episodes to {filename}")
    except Exception as e:
        print(f"Error saving episodes to file: {e}")

def load_episodes_from_json(filename=DETAILED_EPISODES_FILE):
    """
    Loads the list of detailed episodes from a JSON file.
    """
    try:
        with open(filename, "r", encoding="utf-8") as file:
            detailed_episodes = json.load(file)
        print(f"Successfully loaded episodes from {filename}")
        return detailed_episodes
    except FileNotFoundError:
        print(f"Error: File {filename} not found.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return []
    except Exception as e:
        print(f"Error loading episodes from file: {e}")
        return []

def remove_duplicates_from_json(data, key="episode_id"):
    """
    Removes duplicate entries from a JSON file based on a specified key.
    """
    try:
        # Remove duplicates
        unique_items = {}
        for item in data:
            unique_items[item[key]] = item  # Overwrite duplicates with the latest occurrence

        # Save the cleaned data back to the file
        cleaned_data = list(unique_items.values())

        print(f"Removed duplicates based on '{key}'.")
        return cleaned_data

    except KeyError as e:
        print(f"Error: Missing key '{e}' in one or more entries.")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and manage podcast episode data.")
    parser.add_argument(
        "-l", "--local",
        action="store_true",
        help="Load from local file instead of downloading."
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Download all episodes (normally it downloads only new ones)"
    )
    args = parser.parse_args()

    if args.all:
        since = None
    else:
        since = get_last_timestamp()

    try:
        if args.local:
            print("Loading downloaded episodes...")
            detailed_episodes = load_episodes_from_json()
            detailed_episodes = remove_duplicates_from_json(detailed_episodes)
            print("Fully listened episodes with details:")
            for episode in detailed_episodes:
                print(episode)
        else:
            print("Downloading episodes...")
            detailed_episodes = get_fully_listened_episodes_with_details(since=since)
            save_episodes_to_json(remove_duplicates_from_json(detailed_episodes))

    except Exception as e:
        print(f"Error: {e}")
