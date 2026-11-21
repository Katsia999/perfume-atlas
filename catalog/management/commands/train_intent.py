import csv
from collections import defaultdict
from tempfile import NamedTemporaryFile

import joblib
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.pipeline import make_pipeline

from catalog.intent import MODEL_PATH, confident_kind
from catalog.search import KINDS


class Command(BaseCommand):
    help = "Обучает классификатор по заранее размеченному CSV и оценивает на отложенных группах."

    def handle(self, *args, **options):
        dataset = settings.BASE_DIR / "data" / "search" / "queries.csv"
        labels = [key for key, _ in KINDS]
        splits = defaultdict(list)
        groups = {}
        seen = set()
        with dataset.open(encoding="utf-8-sig", newline="") as stream:
            for line, row in enumerate(csv.DictReader(stream), start=2):
                query, label, group, split = (row[field].strip() for field in (
                    "query", "label", "group", "split"
                ))
                if not query or not group or label not in labels or split not in {"train", "test"}:
                    raise CommandError(f"{dataset.name}:{line}: неверный запрос, класс, группа или часть.")
                normalized = " ".join(query.lower().replace("ё", "е").split())
                if normalized in seen or groups.setdefault(group, (label, split)) != (label, split):
                    raise CommandError(f"{dataset.name}:{line}: дубликат запроса или пересечение групп.")
                seen.add(normalized)
                splits[split].append((query, label))

        for split in ("train", "test"):
            if {label for _, label in splits[split]} != set(labels):
                raise CommandError(f"Часть {split} должна содержать все четыре класса.")
        self.stdout.write(
            f"Обучение — {len(splits['train'])}, отложенная проверка — {len(splits['test'])}, "
            f"групп — {len(groups)}."
        )
        train_queries, train_labels = zip(*splits["train"])
        test_queries, test_labels = zip(*splits["test"])
        model = make_pipeline(
            TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True),
            LogisticRegression(C=5, max_iter=1000, random_state=42),
        )
        model.fit(train_queries, train_labels)
        predicted = model.predict(test_queries)
        macro_f1 = f1_score(test_labels, predicted, labels=labels, average="macro")
        self.stdout.write(f"Macro-F1: {macro_f1:.4f}")
        self.stdout.write(classification_report(test_labels, predicted, labels=labels, zero_division=0))
        confident = [confident_kind(model.classes_, p) for p in model.predict_proba(test_queries)]
        correct = sum(guess == label for guess, label in zip(confident, test_labels))
        self.stdout.write(f"При пороге сайта: {sum(bool(label) for label in confident)} уверенных, {correct} верных.")
        for query, expected, guess in zip(test_queries, test_labels, predicted):
            if expected != guess:
                self.stdout.write(f"Ошибка: {query} [{expected} → {guess}]")

        MODEL_PATH.parent.mkdir(exist_ok=True)
        with NamedTemporaryFile(dir=MODEL_PATH.parent, delete=False) as temporary:
            path = MODEL_PATH.parent / temporary.name
        try:
            joblib.dump(model, path)
            path.replace(MODEL_PATH)
        finally:
            path.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Модель сохранена в {MODEL_PATH.relative_to(settings.BASE_DIR)}"))
