import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "rag"))

from embeddings import GeminiEmbedder, format_gemini_document, format_gemini_query


class GeminiFormattingTests(unittest.TestCase):
    def test_format_gemini_query_prefix(self):
        self.assertEqual(
            format_gemini_query("what is dharma"),
            "task: search result | query: what is dharma",
        )

    def test_format_gemini_document_with_title(self):
        self.assertEqual(
            format_gemini_document("verse text", title="Bhagavad Gita"),
            "title: Bhagavad Gita | text: verse text",
        )

    def test_format_gemini_document_default_title(self):
        self.assertEqual(
            format_gemini_document("verse text"),
            "title: none | text: verse text",
        )


class _FakePart:
    @staticmethod
    def from_text(text: str):
        return {"text": text}


class _FakeContent:
    def __init__(self, parts):
        self.parts = parts


class _FakeEmbedContentConfig:
    def __init__(self, output_dimensionality: int):
        self.output_dimensionality = output_dimensionality
        self.task_type = None


class _FakeTypes:
    Part = _FakePart
    Content = _FakeContent
    EmbedContentConfig = _FakeEmbedContentConfig


class _FakeEmbedding:
    def __init__(self, values):
        self.values = values


class _FakeResult:
    def __init__(self, count: int, dims: int):
        self.embeddings = [_FakeEmbedding([float(i)] * dims) for i in range(count)]


class _FakeModels:
    def __init__(self):
        self.calls = []

    def embed_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return _FakeResult(len(contents), config.output_dimensionality)


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


class GeminiEmbedderBatchTests(unittest.TestCase):
    def _embedder(self) -> tuple[GeminiEmbedder, _FakeClient]:
        client = _FakeClient()
        embedder = GeminiEmbedder.__new__(GeminiEmbedder)
        embedder.client = client
        embedder.types = _FakeTypes
        embedder.model = "gemini-embedding-2"
        embedder.dims = 1536
        embedder.batch_size = 50
        embedder.batch_delay = 0
        return embedder, client

    def test_documents_are_wrapped_as_separate_content_objects(self):
        embedder, client = self._embedder()

        embeddings = embedder._embed_batch(["first", "second"], as_query=False)

        self.assertEqual(len(embeddings), 2)
        call = client.models.calls[0]
        self.assertEqual(call["model"], "gemini-embedding-2")
        self.assertEqual(call["config"].output_dimensionality, 1536)
        self.assertIsNone(call["config"].task_type)
        self.assertEqual(len(call["contents"]), 2)
        self.assertEqual(call["contents"][0].parts[0]["text"], "title: none | text: first")
        self.assertEqual(call["contents"][1].parts[0]["text"], "title: none | text: second")

    def test_queries_use_prompt_prefix_not_task_type(self):
        embedder, client = self._embedder()

        embedding = embedder._embed_batch(["what is dharma"], as_query=True)[0]

        self.assertEqual(len(embedding), 1536)
        call = client.models.calls[0]
        self.assertIsNone(call["config"].task_type)
        self.assertEqual(
            call["contents"][0].parts[0]["text"],
            "task: search result | query: what is dharma",
        )


if __name__ == "__main__":
    unittest.main()
