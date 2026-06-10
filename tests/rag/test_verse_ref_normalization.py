"""normalize_verse_ref must emit IDs that exist in final/verses_enriched.json.

Regression for two audit findings: Yajurveda IDs carry the recension segment
(yv_madhyadina_*), and Upanishad IDs are flat per-text sequence numbers
(upanishad_<name>_upanishad_<n>) with no valli/section structure.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

# Load scripts/rag/agent/tools.py under a unique module name. A plain
# `from agent.tools import ...` would return english-v1-rag's agent package
# whenever a test that imports english_config ran earlier in the session
# (english_config puts english-v1-rag first on sys.path and `agent` is then
# cached in sys.modules).
_TOOLS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "rag" / "agent" / "tools.py"
sys.path.insert(0, str(_TOOLS_PATH.parent.parent))

_spec = importlib.util.spec_from_file_location("_full_corpus_agent_tools", _TOOLS_PATH)
_tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tools)
normalize_verse_ref = _tools.normalize_verse_ref


class EpicAndVedaRefTests(unittest.TestCase):
    def test_bhagavad_gita(self):
        self.assertEqual(normalize_verse_ref("BG 2.47"), "bg_2_47")

    def test_rigveda(self):
        self.assertEqual(normalize_verse_ref("RV 1.1.1"), "rv_1_1_1")

    def test_atharvaveda(self):
        self.assertEqual(normalize_verse_ref("AV 1.1.1"), "av_1_1_1")

    def test_yajurveda_uses_madhyadina_recension_ids(self):
        self.assertEqual(normalize_verse_ref("YV 1.1"), "yv_madhyadina_1_1")
        self.assertEqual(normalize_verse_ref("yv 19.30"), "yv_madhyadina_19_30")

    def test_valmiki_ramayana(self):
        self.assertEqual(normalize_verse_ref("VR 1.1.1"), "vr_1_1_1")

    def test_mahabharata(self):
        self.assertEqual(normalize_verse_ref("MBhCE 1.1.1"), "mbhce_1_1_1")
        self.assertEqual(normalize_verse_ref("MBh 1.1.1"), "mbhce_1_1_1")

    def test_ramcharitmanas(self):
        self.assertEqual(normalize_verse_ref("RCM 1.1"), "rcm_1_1")


class UpanishadRefTests(unittest.TestCase):
    def test_single_number_refs_map_to_flat_ids(self):
        self.assertEqual(normalize_verse_ref("Isha Up 1"), "upanishad_isha_upanishad_1")
        self.assertEqual(
            normalize_verse_ref("Isha Upanishad 18"), "upanishad_isha_upanishad_18"
        )
        self.assertEqual(normalize_verse_ref("Katha Up 23"), "upanishad_katha_upanishad_23")
        self.assertEqual(normalize_verse_ref("Mandukya 7"), "upanishad_mandukya_upanishad_7")
        self.assertEqual(normalize_verse_ref("Isha Up. 3"), "upanishad_isha_upanishad_3")

    def test_name_variants_canonicalize(self):
        self.assertEqual(
            normalize_verse_ref("Brihad Up 5"), "upanishad_brihadaranyaka_upanishad_5"
        )
        self.assertEqual(
            normalize_verse_ref("Brihadaranyaka Upanishad 104"),
            "upanishad_brihadaranyaka_upanishad_104",
        )
        self.assertEqual(
            normalize_verse_ref("Shvetashvatara Up 10"),
            "upanishad_svetasvatara_upanishad_10",
        )
        self.assertEqual(
            normalize_verse_ref("Prasna Up 4"), "upanishad_prashna_upanishad_4"
        )

    def test_dotted_upanishad_refs_are_not_mapped(self):
        # The corpus has no valli/section structure, so a dotted ref must not
        # silently produce a plausible-but-wrong flat ID.
        result = normalize_verse_ref("Katha Up 1.2.12")
        self.assertFalse(result.startswith("upanishad_"))

    def test_non_upanishad_names_fall_through(self):
        # A single trailing number after an unknown name must not be treated
        # as an Upanishad ref.
        self.assertEqual(normalize_verse_ref("Gita 47"), "gita_47")


class PassthroughTests(unittest.TestCase):
    def test_internal_ids_unchanged(self):
        self.assertEqual(normalize_verse_ref("bg_2_47"), "bg_2_47")
        self.assertEqual(
            normalize_verse_ref("upanishad_isha_upanishad_1"),
            "upanishad_isha_upanishad_1",
        )
        self.assertEqual(normalize_verse_ref("yv_madhyadina_1_1"), "yv_madhyadina_1_1")


if __name__ == "__main__":
    unittest.main()
