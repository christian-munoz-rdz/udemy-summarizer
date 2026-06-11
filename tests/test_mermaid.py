import re
from unittest.mock import patch

import requests
import responses

from udemy_summarizer.mermaid import MERMAID_INK_URL, render_mermaid

URL_RE = re.compile(re.escape(MERMAID_INK_URL) + ".*")
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


@responses.activate
def test_render_mermaid_ok():
    responses.add(responses.GET, URL_RE, body=FAKE_PNG, status=200)
    assert render_mermaid("flowchart LR\n A --> B") == FAKE_PNG


@responses.activate
def test_render_mermaid_http_error_returns_none():
    responses.add(responses.GET, URL_RE, status=500)
    assert render_mermaid("flowchart LR\n A --> B") is None


@responses.activate
def test_render_mermaid_non_png_returns_none():
    responses.add(responses.GET, URL_RE, body="<html>error</html>", status=200)
    assert render_mermaid("flowchart LR\n A --> B") is None


def test_render_mermaid_network_failure_returns_none():
    with patch("udemy_summarizer.mermaid.requests.get",
               side_effect=requests.ConnectionError("sin red")):
        assert render_mermaid("flowchart LR\n A --> B") is None
