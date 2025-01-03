# Podcast2Anki

Generate flashcards for Anki from your podcasts

# Installation

* Download / Clone the repository
* Install [faster-whipser](https://github.com/SYSTRAN/faster-whisper)
* Create an `.env` file:
```
API_BASE_URL = "your-gpodder-podcast-server.org/api/2/"
USERNAME = "user"
PASSWORD = "password"
OPENAI_API_KEY = "open-ai-api-key"
WHISPER_MODEL = "small"
OPENAI_MODEL = "gpt-4o-mini"
PROMPT = "Summarize the transcript in up to 10 key points. For each point, provide up to 3 full multi-sentence quotes as supporting evidence:"
```

# Usage

1. Download podcast episodes
```
python3 download_podcast.py
```

2. Download & Transcribe podcasts (using `faster-whipser`)
```
python3 process_podcast.py
```

3. Generate summary with key quotes and cards for Anki
```
python3 create_anki_cards.py
```

4. Import the `results/anki-flashcards.csv` file in Anki
