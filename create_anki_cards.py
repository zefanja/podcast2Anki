#!/usr/bin/python3

import os
import json
import csv
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
import markdown
import re
import time

load_dotenv()

# Directories and files
RESULTS_DIR = "results"
TRANSCRIPT_DIR = "transcripts"
RESULTS_FILE = f"{RESULTS_DIR}/flashcard_results.json"
DETAILED_EPISODES_FILE = f"{RESULTS_DIR}/detailed_episodes.json"
OUTPUT_FILE = f"{RESULTS_DIR}/anki_flashcards.csv"
TASKS_FILE = f"{RESULTS_DIR}/batch_tasks.jsonl"
BATCH_OUTPUT_FILE = f"{RESULTS_DIR}/batch_output.jsonl"
BATCH_ID_TMP_FILE = f"{RESULTS_DIR}/last_batch_id"
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
PROMPT = os.getenv("PROMPT")
if not PROMPT:
    PROMPT = "Summarize the transcript in up to 10 key points. For each point, provide up to 3 full multi-sentence quotes as supporting evidence:"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def confirm_continue():
    """
    Prompt the user to confirm whether they want to continue.
    Returns:
        bool: True if the user confirms, False otherwise.
    """
    while True:
        response = input("Do you want to continue? (yes/no): ").strip().lower()
        if response in ['yes', 'y']:
            return True
        elif response in ['no', 'n']:
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

def check_for_tmp_batch_id(file_path=BATCH_ID_TMP_FILE):
    if not os.path.exists(file_path):
        return False

    try:
        with open(file_path, "r") as file:
            return file.read()
    except IOError as e:
        raise IOError(f"An error occurred while reading the file: {e}")

def remove_batch_id_tmp_file(file_path=BATCH_ID_TMP_FILE):
    try:
        os.remove(file_path)
        print(f"{file_path} has been deleted successfully.")
    except FileNotFoundError:
        print(f"{file_path} does not exist.")
    except PermissionError:
        print(f"Permission denied: Unable to delete {file_path}.")
    except Exception as e:
        print(f"An error occurred: {e}")

def load_transcript(episode_id):
    """
    Loads the transcript for a given episode ID.
    """
    transcript_path = os.path.join(TRANSCRIPT_DIR, f"{episode_id}.txt")
    if not os.path.exists(transcript_path):
        #print(f"Transcript for episode {episode_id} not found.")
        return None
    with open(transcript_path, "r", encoding="utf-8") as file:
        return file.read()

def load_results():
    """
    Loads the existing results from the JSON file.
    """
    if not os.path.exists(RESULTS_FILE):
        return {}
    with open(RESULTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_results(results):
    """
    Saves the updated results to the JSON file.
    """
    print("Saving results....")
    with open(RESULTS_FILE, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

def load_episode_metadata():
    """
    Loads episode metadata from the detailed_episodes.json file.
    """
    if not os.path.exists(DETAILED_EPISODES_FILE):
        raise FileNotFoundError(f"{DETAILED_EPISODES_FILE} not found.")
    with open(DETAILED_EPISODES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def check_missing_results(episode_metadata, results):
    """
    Checks for missing results by comparing episode metadata and AI results.
    Returns a list of missing episode IDs.
    """
    all_episode_ids = {episode["episode_id"] for episode in episode_metadata}
    completed_episode_ids = set(results.keys())
    missing_episode_ids = all_episode_ids - completed_episode_ids
    return list(missing_episode_ids)

def create_jsonl_file(transcripts, filename=TASKS_FILE):
    """
    Creates a JSONL file for the batch tasks.
    """
    with open(filename, "w", encoding="utf-8") as file:
        for episode_id, transcript in transcripts.items():
            task = {
                "custom_id": episode_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": OPENAI_MODEL,
                    "messages": [
                        {"role": "user", "content": f"{PROMPT}\n{transcript}"}
                    ]
                }
            }
            file.write(json.dumps(task) + "\n")
    print(f"JSONL file created: {filename}")

def upload_jsonl_file(filename):
    """
    Uploads the JSONL file to OpenAI for batch processing.
    """
    response = client.files.create(
        file=open(filename, "rb"),
        purpose="batch"
    )

    print(f"Uploaded JSONL file: {response.id}")

    return response.id

def create_batch_request(batch_input_file_id):
    """
    Creates a batch request using the uploaded JSONL file.
    """
    batch = client.batches.create(
        input_file_id=batch_input_file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={
            "description": "podcast2anki job"
        }
    )
    # store value temporarly
    with open(BATCH_ID_TMP_FILE, "w") as file:
        file.write(batch.id)

    return batch.id

def poll_batch_status(batch_id):
    """
    Polls the status of a batch request until it is complete.
    """
    while True:
        batch = client.batches.retrieve(batch_id)
        if batch.status == "completed":
            print(batch.output_file_id)
            return batch.output_file_id
        elif batch.status in {"failed", "cancelled"}:
            raise RuntimeError(f"Batch {batch_id} failed with status: {batch.status}")
        print(f"Batch {batch_id} status: {batch.status}... waiting...")
        time.sleep(10)

def download_batch_results(batch_id, output_filename=BATCH_OUTPUT_FILE):
    """
    Downloads the results of a completed batch job from OpenAI's Batch API.

    Args:
        output_file_id (str): The ID of the output file from the batch job.
        output_filename (str): The name of the local file to save the results to.

    Returns:
        list: A list of parsed results from the JSONL file.
    """

    # Download the output file content
    file_response = client.files.content(batch_id)

    # Save the file content locally
    with open(output_filename, "w", encoding="utf-8") as file:
        file.write(file_response.text)

    print(f"Results saved to {output_filename}")

    # delete temp stored batch id
    remove_batch_id_tmp_file()

    # Parse the JSONL file content
    results = []
    with open(output_filename, "r", encoding="utf-8") as file:
        for line in file:
            results.append(json.loads(line))

    return output_filename

def process_batch_results(output_filename):
    """
    Parses a JSONL file into a dictionary.
    Keys are `custom_id` from each record where `status_code` is 200,
    and values are lists of parsed content points from the `choices` array.

    :param file_path: Path to the JSONL file.
    :return: Dictionary with parsed data.
    """
    result = {}
    pattern = re.compile(r'^\d+\.\s+(.*)')  # Matches numbers followed by a period and text
    is_first_subitem = False  # Tracks if it's the first sub-item after a main point

    with open(output_filename, 'r', encoding='utf-8') as file:
        for line in file:
            try:
                record = json.loads(line.strip())

                # Extract `custom_id` and `response` fields
                custom_id = record.get("custom_id")
                response = record.get("response", {})

                # Check if status_code is 200
                if response.get("status_code") == 200:
                    # Get content from the choices array
                    choices = response.get("body", {}).get("choices", [])

                    for choice in choices:
                        content = choice.get("message", {}).get("content", "")

                    # Parse content into numbered points with sub-items
                    points = []
                    current_point = []

                    for line in content.split("\n"):
                        line = line.strip()
                        if not line:
                            continue

                        match = pattern.match(line)
                        if match:
                            # Extract and clean the text, removing the leading number and period
                            content = match.group(1).strip()
                            if current_point:
                                points.append("\n".join(current_point))
                            current_point = []
                            current_point.append(content)
                            is_first_subitem = True  # Reset for detecting the first sub-item
                        elif line.strip().startswith('-'):
                            if is_first_subitem:
                                # Add a blank line before the first sub-item
                                current_point.append('')
                                is_first_subitem = False
                            current_point.append(line)
                        else:
                            current_point.append(line)

                    result[custom_id] = points

            except json.JSONDecodeError as e:
                print(f"Skipping invalid JSON line: {line.strip()} Error: {e}")

    return result



def create_flashcards_for_episode(episode_id, metadata, ai_result):
    """
    Prepares a flashcard entry for Anki.
    """
    return {
        "author": metadata.get("podcast_author", "Unknown"),
        "date": metadata.get("date", datetime.now().strftime("%Y-%m-%d")),
        "title": f'{metadata.get("podcast_title", "Unknown Podcast")} - {metadata.get("episode_title", "Unknown Episode")}',
        "quote": markdown.markdown(ai_result.strip())
    }

def save_flashcards_to_csv(flashcards, filename=OUTPUT_FILE):
    """
    Saves flashcards to a CSV file in a format Anki can import.
    """
    with open(filename, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        for flashcard in flashcards:
            writer.writerow([flashcard["quote"], flashcard["title"], flashcard["author"], flashcard["date"]])
    print(f"Flashcards saved to {filename}")

def create_new_batch(new_transcripts):
    create_jsonl_file(new_transcripts)
    file_id = upload_jsonl_file(TASKS_FILE)
    batch_id = create_batch_request(file_id)

    return batch_id

def main():
    """
    Main function to generate flashcards for multiple episodes.
    """
    episode_metadata = load_episode_metadata()
    results = load_results()

    # Check for missing results
    missing_episode_ids = check_missing_results(episode_metadata, results)
    if missing_episode_ids:
        #print(f"Missing results for {len(missing_episode_ids)} episodes: {missing_episode_ids}")
        print(f"Missing results for {len(missing_episode_ids)} episodes")
    else:
        print("All episodes have AI-generated results.")

    new_transcripts = {}

    # Load transcripts for processing
    for episode in episode_metadata:
        if episode["episode_id"] in missing_episode_ids:
            transcript = load_transcript(episode["episode_id"])
            if transcript:
                new_transcripts[episode["episode_id"]] = transcript

    # Generate flashcards for new transcripts
    if new_transcripts:
        print(f"Generating flashcards for {len(new_transcripts)} new episodes...")

        if confirm_continue():
            print("Continuing...")
            batch_id = check_for_tmp_batch_id()

            if not batch_id:
                batch_id = create_new_batch(new_transcripts)

            output_file_id = poll_batch_status(batch_id)
            output_filename = download_batch_results(output_file_id)
            ai_results = process_batch_results(output_filename)
            results.update(ai_results)
            save_results(results)

            # Create Anki flashcards
            flashcards = []
            for episode in episode_metadata:
                episode_id = episode["episode_id"]
                if episode_id in results:
                    for item in results[episode_id]:
                        flashcards.append(create_flashcards_for_episode(
                            episode_id=episode_id,
                            metadata=episode,
                            ai_result=item
                        ))

            # Save flashcards to CSV
            save_flashcards_to_csv(flashcards)
        else:
            print("Exiting...")

if __name__ == "__main__":
    main()