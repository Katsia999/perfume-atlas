from hashlib import file_digest
from pathlib import Path
from shutil import copyfileobj
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from catalog import semantic
from catalog.search import documents


def download_file(filename, url, digest):
    target = semantic.MODEL_DIR / filename
    if target.is_file():
        with target.open("rb") as stream:
            if file_digest(stream, "sha256").hexdigest() == digest:
                return
    with NamedTemporaryFile(dir=target.parent, delete=False) as temp:
        pending = Path(temp.name)
    try:
        with urlopen(url, timeout=120) as source, pending.open("wb") as dest:
            copyfileobj(source, dest)
        with pending.open("rb") as stream:
            if file_digest(stream, "sha256").hexdigest() != digest:
                raise CommandError(f"Контрольная сумма {filename} не совпала. Повторите загрузку.")
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)


class Command(BaseCommand):
    help = "Загрузить ruBERT-mini-FRIDA и подготовить векторы опубликованных записей."

    def handle(self, *args, **options):
        semantic.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        for filename, (url, digest) in semantic.MODEL_FILES.items():
            self.stdout.write(filename)
            download_file(filename, url, digest)
        texts = dict.fromkeys(text for record in documents() for text, _ in semantic.passages_with_titles(record))
        vectors = [semantic.passage_vector(text) for text in texts]
        with NamedTemporaryFile(dir=semantic.MODEL_DIR, delete=False) as temp:
            pending = Path(temp.name)
        try:
            with pending.open("wb") as output:
                np.savez(output, keys=[semantic.passage_key(text) for text in texts], vectors=vectors)
            pending.replace(semantic.INDEX_PATH)
        finally:
            pending.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Модель готова. Фрагментов каталога: {len(texts)}."))
