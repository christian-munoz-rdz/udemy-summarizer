from unittest.mock import MagicMock

import anthropic
import httpx

from udemy_summarizer.models import Lecture, Section
from udemy_summarizer.summarizer import Summarizer


def _make_section(transcript="Contenido de la lección."):
    return Section(
        index=1,
        title="Variables",
        lectures=[Lecture(id=1, title="Intro", object_index=1, type="video",
                          transcript=transcript)],
    )


def _mock_client(response_text="## Conceptos clave\nResumen."):
    client = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = response_text
    message = MagicMock()
    message.content = [block]
    stream_cm = client.messages.stream.return_value
    stream_cm.__enter__.return_value.get_final_message.return_value = message
    return client


def test_summarize_section_returns_text():
    client = _mock_client()
    summarizer = Summarizer(client=client)
    summary = summarizer.summarize_section("Curso X", _make_section())
    assert summary == "## Conceptos clave\nResumen."
    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert "Variables" in kwargs["messages"][0]["content"]


def test_summarize_section_without_transcripts_returns_none():
    summarizer = Summarizer(client=_mock_client())
    section = _make_section(transcript=None)
    assert summarizer.summarize_section("Curso X", section) is None


def test_summarize_section_degrades_on_api_error():
    client = MagicMock()
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, request=request)
    client.messages.stream.side_effect = anthropic.RateLimitError(
        "rate limited", response=response, body=None
    )
    summarizer = Summarizer(client=client)
    assert summarizer.summarize_section("Curso X", _make_section()) is None


def test_chunking_for_long_sections():
    client = _mock_client()
    summarizer = Summarizer(client=client)
    # Texto enorme: fuerza el camino map-reduce
    long_text = "palabra " * 200_000  # ~1.6M chars > 150K tokens estimados
    section = Section(
        index=1,
        title="Larga",
        lectures=[
            Lecture(id=i, title=f"L{i}", object_index=i, type="video", transcript=long_text)
            for i in range(3)
        ],
    )
    summary = summarizer.summarize_section("Curso X", section)
    assert summary is not None
    # map (≥2 chunks) + reduce (1 llamada final)
    assert client.messages.stream.call_count >= 3
