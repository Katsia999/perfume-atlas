import json
from pathlib import Path

from django.conf import settings


def local_bottle_photos(entries):
    if not settings.DEBUG or not entries:
        return {}

    photo_root = settings.LOCAL_BOTTLE_PHOTO_ROOT
    manifest = photo_root.with_suffix(".json")
    try:
        photos = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}

    by_version = {(photo["brand"], photo["name"], photo["version"]): photo for photo in photos}
    result = {}
    for entry in entries:
        photo = by_version.get((entry.brand.name, entry.name, entry.version))
        if photo is None:
            continue

        filename = Path(photo["filename"]).name
        if (photo_root / filename).is_file():
            result[entry.pk] = {
                "url": settings.LOCAL_BOTTLE_PHOTO_URL + filename,
                "width": photo["width"],
                "height": photo["height"],
                "credit": photo.get("credit") or f"Фото производителя · {entry.brand.name}",
            }
    return result
