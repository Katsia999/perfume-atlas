import csv
from datetime import date
from hashlib import sha256
from pathlib import Path
import re
from unittest.mock import patch

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from catalog.intent import MODEL_PATH
from catalog.search import FRAGRANCE, documents, search


EVALUATION_DATE = date(2026, 11, 21)
LABELS_SHA256 = "1a9dd65824d2b4c48d2761fc96b5684cfa57d6567640f40ba3f80818af0a63f6"
TOKEN = re.compile(r"[^\W_]+")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def tokens(text):
    return set(TOKEN.findall(text.casefold()))


def baseline(query, index):
    query_words = tokens(query)
    matches = [(-len(query_words & document_words), identifier)
               for identifier, document_words in index.items()]
    return [identifier for score, identifier in sorted(matches) if score < 0]


def stable_id(record, fragrance_codes):
    if record.kind == FRAGRANCE:
        entry = record.entry
        return fragrance_codes[(entry.brand.name, entry.name, entry.version)]
    return f"{record.kind}:{record.title}"


def outcome(ranked_ids, relevant_ids):
    if relevant_ids:
        return "hit" if relevant_ids.intersection(ranked_ids[:3]) else "miss"
    return "non_empty" if ranked_ids else "empty"


class Command(BaseCommand):
    help = "Сравнивает поиск сайта и поиск по словам на демонстрационной базе."

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path, required=True, help="Куда записать таблицу CSV.")

    def handle(self, *args, **options):
        data = settings.BASE_DIR / "data"
        label_path = data / "search" / "evaluation.csv"
        label_hash = sha256(label_path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()
        if label_hash != LABELS_SHA256:
            raise CommandError("Контрольная сумма разметки изменилась.")
        if not MODEL_PATH.is_file():
            raise CommandError("Сначала обучите модель командой train_intent.")
        if settings.TIME_ZONE != "Europe/Moscow":
            raise CommandError("Для оценки свежести ожидается настройка Europe/Moscow.")

        scenarios = read_csv(label_path)
        fragrance_codes = {
            (row["brand"], row["name"], row["version"]): row["code"]
            for row in read_csv(data / "demo" / "fragrances.csv")
        }
        expected_ids = set(fragrance_codes.values()) | {
            f'{row["kind"]}:{row["title"]}' for row in read_csv(data / "demo" / "materials.csv")
        }
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            try:
                index = {
                    stable_id(record, fragrance_codes): tokens(f"{record.title} {record.entry.description}")
                    for record in documents()
                }
            except KeyError as error:
                raise CommandError("В опубликованном каталоге есть версии вне демонстрационного набора.") from error
            if set(index) != expected_ids:
                raise CommandError("Нужна база со всеми 27 демонстрационными публикациями без дополнительных.")

            results = []
            with patch("catalog.search.timezone.localdate", return_value=EVALUATION_DATE):
                for scenario in scenarios:
                    relevant_ids = set(scenario["relevant_ids"].split("|")) - {""}
                    if not relevant_ids <= expected_ids:
                        raise CommandError(f'Неизвестная запись в сценарии {scenario["id"]}.')
                    query = scenario["query"]
                    baseline_ids = baseline(query, index)
                    response = search(query)
                    smart_ids = [stable_id(record, fragrance_codes) for record in response.results]
                    results.append({
                        **scenario,
                        "baseline_top3": "|".join(baseline_ids[:3]),
                        "baseline_count": len(baseline_ids),
                        "baseline_outcome": outcome(baseline_ids, relevant_ids),
                        "smart_top3": "|".join(smart_ids[:3]),
                        "smart_count": len(smart_ids),
                        "smart_outcome": outcome(smart_ids, relevant_ids),
                        "effective_query": response.effective_query,
                        "since": response.since,
                        "until": response.until,
                    })

        with options["output"].open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(results[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(results)
        answerable = sum(bool(row["relevant_ids"]) for row in results)
        unanswerable = len(results) - answerable
        self.stdout.write(f"Дата оценки {EVALUATION_DATE}, Europe/Moscow. Публикаций: {len(index)}.")
        self.stdout.write(f"SHA-256 модели: {sha256(MODEL_PATH.read_bytes()).hexdigest()}")
        for method in ("baseline", "smart"):
            hits = sum(row[f"{method}_outcome"] == "hit" for row in results)
            empty = sum(row[f"{method}_outcome"] == "empty" for row in results)
            self.stdout.write(f"{method}: Hit@3 {hits}/{answerable} ({hits / answerable:.1%}), "
                              f"пустых выдач при отсутствии ответа {empty}/{unanswerable}.")
