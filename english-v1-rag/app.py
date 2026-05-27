"""Flask web interface: full multilingual corpus at ``/``, English beta at ``/beta``.

Local / Docker use this entrypoint (port 5002). Vercel imports root ``app.py``.

Shared route logic: ``scripts/rag/app_factory.py``.
"""

from app_bootstrap import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
