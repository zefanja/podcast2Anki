# Podcast2Anki

Generate flashcards for Anki from your podcasts! You have to sync your podcasts to gpodder or a compatible server first (e.g. [oPodSync](https://github.com/kd2org/opodsync)).

# Installation

* Download / Clone the repository
* Create an `.env` file:
```
API_BASE_URL = "your-gpodder-podcast-server.org/api/2/"
USERNAME = "user"
PASSWORD = "password"
OPENAI_API_KEY = "open-ai-api-key"
OPENAI_MODEL = "gpt-4o-mini"
PROMPT = "Summarize the transcript in up to 10 key points. For each point, provide up to 3 full multi-sentence quotes as supporting evidence:"
```

# Usage

1. Download podcast episodes
```
python3 download_podcast.py
```

2. Download & Transcribe podcasts
```
python3 process_podcast.py
```

3. Generate summary with key quotes and cards for Anki
```
python3 create_anki_cards.py
```

4. Import the `results/anki-flashcards.csv` file in Anki (no headers, comma delimiter → `key_point,podcast_title,author,date`)

# License
GPLv3