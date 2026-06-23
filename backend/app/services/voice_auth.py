import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav

encoder = VoiceEncoder()
SAMPLE_RATE = 16000
CHUNK_SECONDS = 1.6
CHUNK_STEP_SECONDS = 0.8


def _normalize_embedding(embedding):
    vector = np.asarray(embedding, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


def extract_embedding(audio_path):
    wav = preprocess_wav(audio_path)
    embeddings = [_normalize_embedding(encoder.embed_utterance(wav))]

    chunk_size = int(SAMPLE_RATE * CHUNK_SECONDS)
    step_size = int(SAMPLE_RATE * CHUNK_STEP_SECONDS)
    if wav.size >= chunk_size * 2:
        for start in range(0, max(wav.size - chunk_size + 1, 0), step_size):
            chunk = wav[start:start + chunk_size]
            if chunk.size < chunk_size:
                continue
            if float(np.sqrt(np.mean(np.square(chunk)))) < 0.005:
                continue
            embeddings.append(_normalize_embedding(encoder.embed_utterance(chunk)))

    averaged = np.mean(np.vstack(embeddings), axis=0)
    return _normalize_embedding(averaged)


def compute_voice_match(probe_embedding, enrolled_embeddings):
    similarities = [compute_similarity(probe_embedding, embedding) for embedding in enrolled_embeddings]
    similarities.sort(reverse=True)

    best_similarity = float(similarities[0]) if similarities else 0.0
    second_best = float(similarities[1]) if len(similarities) > 1 else 0.0
    top3 = similarities[:3]
    avg_top3_similarity = float(sum(top3) / len(top3)) if top3 else 0.0

    centroid_similarity = 0.0
    if enrolled_embeddings:
        enrolled = np.vstack([_normalize_embedding(embedding) for embedding in enrolled_embeddings])
        centroid = _normalize_embedding(np.mean(enrolled, axis=0))
        centroid_similarity = compute_similarity(probe_embedding, centroid)

    primary_similarity = max(best_similarity, centroid_similarity)
    decision_rule = "best_similarity" if best_similarity >= centroid_similarity else "centroid_similarity"
    return {
        "primary_similarity": float(primary_similarity),
        "best_similarity": best_similarity,
        "second_best_similarity": second_best,
        "avg_top3_similarity": avg_top3_similarity,
        "centroid_similarity": float(centroid_similarity),
        "match_margin": float(best_similarity - second_best),
        "decision_rule": decision_rule,
    }


def compute_similarity(emb1, emb2):
    a = np.asarray(emb1, dtype=np.float32)
    b = np.asarray(emb2, dtype=np.float32)
    if a.size == 0 or b.size == 0:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)
