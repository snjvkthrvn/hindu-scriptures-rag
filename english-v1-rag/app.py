"""Flask web interface: English corpus at ``/``, full corpus at ``/main``.

Railway / Docker / production use this entrypoint (port 5002).

Shared route logic: ``scripts/rag/app_factory.py``.
"""

import json

# Import english_config first: it inserts ``english-v1-rag`` and ``scripts/rag`` on sys.path.
from english_config import ENGLISH_VERSES_FILE, get_english_config

from app_factory import create_dual_app

ENGLISH_FILTERS = {"sources": [], "categories": [], "traditions": [], "total_verses": 0}

try:
    with open(ENGLISH_VERSES_FILE) as f:
        _verses = json.load(f)
    _sources, _categories, _traditions = set(), set(), set()
    for v in _verses:
        s = v.get("source", {}).get("text", "")
        c = v.get("metadata", {}).get("category", "")
        t = v.get("metadata", {}).get("tradition", "")
        if s:
            _sources.add(s)
        if c:
            _categories.add(c)
        if t:
            _traditions.add(t)
    ENGLISH_FILTERS = {
        "sources": sorted(_sources),
        "categories": sorted(_categories),
        "traditions": sorted(_traditions),
        "total_verses": len(_verses),
    }
    del _verses, _sources, _categories, _traditions
except FileNotFoundError:
    pass

app = create_dual_app(get_english_config(), ENGLISH_FILTERS)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
