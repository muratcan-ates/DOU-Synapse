"""The docs shell must ship every local stylesheet and script it references."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

from httpx import AsyncClient


class DocsAssets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paths: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        path = None
        if tag == "script":
            path = values.get("src")
        elif tag == "link" and values.get("rel") == "stylesheet":
            path = values.get("href")
        if path is not None:
            self.paths.add(path)


async def test_docs_referenced_assets_are_available(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200
    assets = DocsAssets()
    assets.feed(response.text)
    assert assets.paths, "The docs shell must reference its local presentation assets."
    for path in sorted(assets.paths):
        assert path.startswith("/static/"), path
        asset = await client.get(path)
        assert asset.status_code == 200, path
        assert asset.content, path
        expected_type = "text/css" if urlsplit(path).path.endswith(".css") else "javascript"
        assert expected_type in asset.headers["content-type"], path
        assert asset.headers["x-content-type-options"] == "nosniff", path
