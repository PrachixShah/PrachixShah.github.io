"""Render only Website Pics into the temporary Pages deployment."""
import hashlib
import html
import io
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

ALBUM = "5D82A2A76E69CF3C!sd53f7b5e97664f97b2bfafddd5bb71dc"
GRAPH = "https://graph.microsoft.com/v1.0"
MARKER = "<!-- album photos -->"


def request(url, *, token=None, data=None):
    headers = {}
    if token:
        if urlsplit(url).netloc != "graph.microsoft.com":
            raise ValueError("Unexpected Graph host")
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, data=data, headers=headers), timeout=60) as response:
        return response.read()


def run(site):
    form = urlencode({
        "client_id": os.environ["MS_CLIENT_ID"],
        "refresh_token": os.environ["MS_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    token = json.loads(request(
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=form
    ))["access_token"]
    base = f"{GRAPH}/me/drive/items/{ALBUM}"
    album = json.loads(request(base, token=token))
    if "album" not in album.get("bundle", {}):
        raise ValueError("Configured source is not a photo album")
    items = {}
    url = base + "/children?$expand=thumbnails"
    while url:
        page = json.loads(request(url, token=token))
        for item in page["value"]:
            items[item["id"]] = item
        url = page.get("@odata.nextLink")
    expected = album["bundle"].get("childCount")
    if expected is not None and len(items) != expected:
        raise ValueError("Album changed during sync; retry")
    out = site / "assets" / "album"
    out.mkdir(parents=True, exist_ok=False)
    figures = []
    def taken(item):
        return (item.get("photo") or {}).get("takenDateTime") or item.get("createdDateTime", "")
    for item in sorted(items.values(), key=taken, reverse=True):
        if not ("photo" in item or "image" in item or
                item.get("file", {}).get("mimeType", "").startswith("image/")):
            continue
        thumbs = item.get("thumbnails")
        if not thumbs:
            thumbs = json.loads(request(f"{GRAPH}/me/drive/items/{item['id']}/thumbnails", token=token))["value"]
        preview = thumbs[0]["large"]["url"]
        name = hashlib.sha256(item["id"].encode()).hexdigest() + ".jpg"
        with Image.open(io.BytesIO(request(preview))) as src:
            img = ImageOps.exif_transpose(src).convert("RGB")
            img.save(out / name, quality=88)
        label = html.escape(item.get("description") or f"Album photo from {taken(item)[:10] or 'Website Pics'}", quote=True)
        figures.append(f'<figure><img src="assets/album/{name}" alt="{label}" loading="lazy" width="{img.width}" height="{img.height}"></figure>')
    p = site / "photos.html"
    template = p.read_text()
    if template.count(MARKER) != 1:
        raise ValueError("Missing unique gallery marker")
    p.write_text(template.replace(MARKER, "\n".join(figures)))
    print(f"Rendered {len(figures)} photos")


if __name__ == "__main__":
    run(Path(sys.argv[1]))
