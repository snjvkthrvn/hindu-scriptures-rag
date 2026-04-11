"""Flask web interface — full corpus only at ``/`` (dev / Makefile ``make web``).

For English + full corpus in one process, use ``english-v1-rag/app.py`` (port 5002).

Implementation lives in ``app_factory.py`` so routes stay in one place.
"""

from app_factory import create_full_app

app = create_full_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
