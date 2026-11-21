from functools import lru_cache

import joblib
from django.conf import settings


MODEL_PATH = settings.BASE_DIR / ".local" / "query-intent.joblib"
MIN_CONFIDENCE = 0.42
MIN_MARGIN = 0.12


@lru_cache(maxsize=1)
def load_model(modified_at):
    return joblib.load(MODEL_PATH)


def confident_kind(labels, probabilities):
    best, second = sorted(zip(probabilities, labels), reverse=True)[:2]
    if best[0] >= MIN_CONFIDENCE and best[0] - second[0] >= MIN_MARGIN:
        return best[1]
    return ""


def preferred_kind(query):
    try:
        modified_at = MODEL_PATH.stat().st_mtime_ns
    except FileNotFoundError:
        return ""
    model = load_model(modified_at)
    return confident_kind(model.classes_, model.predict_proba([query])[0])
