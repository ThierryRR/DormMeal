# Deployment

## Local
```bash
pip install -r requirements-dev.txt
streamlit run app.py            # http://localhost:8501
```
Optional: `export GEMINI_API_KEY=...` to let Gemini parse free-text requests and events.
Without a key the rule-based parser is used. Numbers never come from the LLM.

## Docker
```bash
docker build -t dormmeal .
docker run -p 8501:8501 -e GEMINI_API_KEY=your_key dormmeal     # key optional
```

## Streamlit Community Cloud (free)
1. Push the repository to GitHub.
2. On share.streamlit.io: *New app*, choose the repository, branch `main`, main file `app.py`.
3. *Advanced settings > Secrets*: `GEMINI_API_KEY = "..."` (optional). Never commit a key:
   `.streamlit/secrets.toml` is in `.gitignore`.
4. The SQLite file `dormmeal.db` is created at start-up from `data/catalog_v1.csv`. On Community Cloud
   the disk is not persistent: likes and saved plans are lost when the app restarts (acceptable for a demo;
   a hosted database would be needed for real users).

## Resource notes
- The optimizer uses 4 CP-SAT workers and up to 20 s per plan; the free tier is enough for a demo.
- Catalog changes: edit `data/catalog_v1.csv`, run `python scripts/validate_catalog.py` and `pytest -q`, push.
