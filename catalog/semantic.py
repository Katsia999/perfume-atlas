"""Local retrieval over passages from published catalogue records."""

from functools import lru_cache
from hashlib import sha256

import numpy as np
from django.conf import settings

from .search_language import words

MODEL_DIR = settings.BASE_DIR / ".local" / "rubert-mini-frida"
MODEL_FILES = {
    "tokenizer.json": (
        "https://huggingface.co/sergeyzh/rubert-mini-frida/resolve/32a82388a9f99c99eca74494731f7ee6e9a9fe3a/tokenizer.json",
        "139995a730139fb2158226e69c5879159c020a71c33c87d65124914663f618ad",
    ),
    "model.onnx": (
        "https://huggingface.co/amekhrishvili/rubert-mini-frida-onnx/resolve/c817d58bb260e030340a936b17e844ddd7f8539d/model.onnx",
        "ac3ea7248d0d514dba5e60a11c50d6b81ff2a2a8d6c149fd15fbd69711b167ba",
    ),
}
INDEX_PATH = MODEL_DIR / "passages-c817d58.npz"


def passages(record):
    yield record.entry.description
    if record.kind == "fragrance":
        yield ", ".join(name for kind, name in record.entities if kind in {"family", "note", "character"})
        for fact in (*record.entry.wear.all(), *record.entry.performance.all()):
            yield fact.description
    else:
        for paragraph in record.entry.body.splitlines():
            tokens = paragraph.split()
            for start in range(0, len(tokens), 80):
                yield " ".join(tokens[start:start + 80])


def passages_with_titles(record):
    for passage in dict.fromkeys(passages(record)):
        if passage.strip():
            yield f"{record.title}. {passage}", passage


@lru_cache(maxsize=1)
def encoder():
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=512)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(MODEL_DIR / "model.onnx"), options,
                                   providers=["CPUExecutionProvider"])
    return tokenizer, session


def encode(text):
    tokenizer, session = encoder()
    ids = np.array([tokenizer.encode(text).ids], dtype=np.int64)
    inputs = {"input_ids": ids, "attention_mask": np.ones_like(ids), "token_type_ids": np.zeros_like(ids)}
    # The exported model already applies mean pooling to the token embeddings.
    vector = session.run(["embeddings"], inputs)[0][0]
    return vector / np.linalg.norm(vector)


def passage_key(text):
    return sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def prepared_vectors():
    if INDEX_PATH.is_file():
        with np.load(INDEX_PATH, allow_pickle=False) as index:
            return dict(zip(index["keys"], index["vectors"]))
    return {}


@lru_cache(maxsize=2048)
def passage_vector(text):
    stored = prepared_vectors().get(passage_key(text))
    return stored if stored is not None else encode("search_document: " + text)


def model_ready():
    return all((MODEL_DIR / filename).is_file() for filename in MODEL_FILES)


def retrieve(query, candidates, normalize, ignored):
    """Rank the best passage per record, after catalogue restrictions have been applied."""
    terms = {word for word in normalize(query) if word not in ignored and len(word) > 2}
    if not terms or not candidates:
        return []
    forms = {form for form in words(query) if terms.intersection(normalize(form))}
    query_vector = encode("search_query: " + query) if model_ready() else None
    ranked = []
    for record in candidates:
        best = None
        for text, snippet in passages_with_titles(record):
            hits = terms.intersection(normalize(text))
            # Stemming alone can merge different Russian words, e.g. «белья» and «белый».
            exact = forms.intersection(words(text))
            coverage = 0.7 * len(hits) / len(terms) + 0.3 * len(exact) / len(forms)
            similarity = float(query_vector @ passage_vector(text)) if query_vector is not None else 0
            score = similarity + 0.18 * coverage
            if best is None or score > best[0]:
                best = (score, similarity, coverage, snippet)
        if best:
            ranked.append((*best, record))
    ranked.sort(key=lambda row: -row[0])
    if not ranked:
        return []
    lead = ranked[0][0]
    # Cosine scores are model-specific. A weak match needs either shared words or
    # a clear lead over another record before it can be shown as a suggestion.
    clear_lead = len(ranked) > 1 and lead - ranked[1][0] >= 0.035
    results = []
    for score, similarity, coverage, snippet, record in ranked[:5]:
        if not coverage and similarity < 0.32 and not (score == lead and clear_lead and similarity >= 0.24):
            continue
        if score >= lead - 0.055 and (query_vector is not None or coverage >= 0.25):
            record.passage = snippet
            results.append(record)
    return results
