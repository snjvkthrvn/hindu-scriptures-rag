"""Flask web interface — full multilingual corpus only at ``/`` (dev / Makefile ``make web``).

For the dual setup (full corpus at ``/``, English beta at ``/beta``) use
``english-v1-rag/app.py`` (port 5002) — that's the production entrypoint.

Implementation lives in ``app_factory.py`` so routes stay in one place.
"""

from app_factory import create_full_app

app = create_full_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
