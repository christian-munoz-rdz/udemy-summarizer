from pathlib import Path

from udemy_summarizer.transcript import (
    html_to_text,
    pick_caption,
    pick_subtitle_language,
    srt_to_text,
    subtitle_to_text,
    vtt_to_text,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_vtt_to_text_strips_metadata_and_dedupes():
    vtt = (FIXTURES / "sample.vtt").read_text(encoding="utf-8")
    text = vtt_to_text(vtt)
    assert "WEBVTT" not in text
    assert "-->" not in text
    assert "<c>" not in text
    assert text.count("Hola y bienvenidos al curso de Python.") == 1
    assert "las variables" in text
    assert "Empecemos con un ejemplo sencillo." in text


def test_pick_caption_exact_locale():
    captions = [
        {"locale_id": "en_US", "url": "http://x/en.vtt"},
        {"locale_id": "es_ES", "url": "http://x/es.vtt"},
    ]
    assert pick_caption(captions, "es_ES")["url"] == "http://x/es.vtt"


def test_pick_caption_language_prefix():
    captions = [{"locale_id": "es_MX", "url": "http://x/esmx.vtt"}]
    assert pick_caption(captions, "es")["url"] == "http://x/esmx.vtt"


def test_pick_caption_fallback():
    captions = [{"locale_id": "en_US", "url": "http://x/en.vtt"}]
    assert pick_caption(captions, "es", "en")["url"] == "http://x/en.vtt"


def test_pick_caption_none():
    assert pick_caption([], "es", "en") is None
    assert pick_caption([{"locale_id": "fr_FR", "url": "u"}], "es", "en") is None


def test_html_to_text():
    html = (
        "<h2>Recursos</h2><p>Descarga el <b>material</b> aquí.</p>"
        "<ul><li>Enlace uno</li><li>Enlace dos</li></ul>"
        "<script>alert('x')</script>"
    )
    text = html_to_text(html)
    assert "Recursos" in text
    assert "Descarga el material aquí." in text
    assert "- Enlace uno" in text
    assert "alert" not in text


def test_srt_to_text():
    srt = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Primera línea.\n\n"
        "2\n"
        "00:00:05,000 --> 00:00:08,000\n"
        "Segunda línea."
    )
    text = srt_to_text(srt)
    assert "Primera línea." in text
    assert "Segunda línea." in text
    assert "-->" not in text


def test_subtitle_to_text_plain():
    assert subtitle_to_text("Texto plano del transcript.", "txt") == "Texto plano del transcript."


def test_pick_subtitle_language():
    subtitles = {"en": "http://x/en.vtt", "es": "http://x/es.vtt"}
    assert pick_subtitle_language(subtitles, "es") == ("es", "http://x/es.vtt")
    assert pick_subtitle_language(subtitles, "es", "en") == ("es", "http://x/es.vtt")
    assert pick_subtitle_language(subtitles, "fr", "en") == ("en", "http://x/en.vtt")
