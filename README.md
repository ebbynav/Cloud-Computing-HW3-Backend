# AI Photo Search Backend

This repository is structured for the Python backend deployment:

- `index_photo.py`
- `search_photo.py`
- `buildspec-index.yml`
- `buildspec-search.yml`
- `template.yaml`
- `README.md`

Build and deploy behavior:

- `buildspec-index.yml` packages `index_photo.py` and updates Lambda `index-photos`.
- `buildspec-search.yml` packages `search_photo.py` and updates Lambda `search-photos`.

Both buildspecs install:

- `opensearch-py`
- `requests`
- `requests-aws4auth`

Frontend files (`index.html`, `app.js`, `styles.css`, `assets/`, and `buildspec-frontend.yml`) should live in a separate frontend repository.
