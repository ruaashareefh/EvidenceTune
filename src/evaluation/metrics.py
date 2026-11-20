
"""Evaluation metrics for EvidenceTune."""

import string
from collections import Counter


# =========================================================
# 1. AUCM CONFUSION MATRIX
# =========================================================

def aucm_counts(
    gold_answerable: list[bool],
    predicted_abstain: list[bool],
    answer_correct: list[bool],
) -> dict[str, int]:
    """
    Compute Answerable-Unanswerable Confusion Matrix (AUCM) counts.

    TP: Answerable question answered correctly.
    FP: Answerable question answered incorrectly,
        or unanswerable question answered.
    FN: Answerable question where the model abstained.
    TN: Unanswerable question where the model abstained.

    Args:
        gold_answerable: Whether each question is answerable.
        predicted_abstain: Whether the model abstained.
        answer_correct: Whether the model's answer was correct.
            Ignored for abstentions and unanswerable questions.

    Returns:
        Dictionary containing TP, FP, FN, and TN counts.

    Raises:
        ValueError: If input lists have different lengths.
    """
    if not (
        len(gold_answerable)
        == len(predicted_abstain)
        == len(answer_correct)
    ):
        raise ValueError("Input lists must have equal lengths")

    counts = {
        "TP": 0,
        "FP": 0,
        "FN": 0,
        "TN": 0,
    }

    for gold, abstain, correct in zip(
        gold_answerable,
        predicted_abstain,
        answer_correct,
        strict=True,
    ):
        if gold and not abstain and correct:
            counts["TP"] += 1

        elif gold and not abstain and not correct:
            counts["FP"] += 1

        elif gold and abstain:
            counts["FN"] += 1

        elif not gold and abstain:
            counts["TN"] += 1

        else:
            # Unanswerable question, but the model answered.
            counts["FP"] += 1

    return counts


# =========================================================
# 2. AUCM PRECISION, RECALL, AND F1
# =========================================================

def aucm_precision(counts: dict[str, int]) -> float:
    """
    Calculate AUCM precision.

    Precision = TP / (TP + FP)

    Returns 0.0 when the denominator is zero.
    """
    tp = counts["TP"]
    fp = counts["FP"]

    denominator = tp + fp

    return tp / denominator if denominator > 0 else 0.0


def aucm_recall(counts: dict[str, int]) -> float:
    """
    Calculate AUCM recall.

    Recall = TP / (TP + FN)

    Returns 0.0 when the denominator is zero.
    """
    tp = counts["TP"]
    fn = counts["FN"]

    denominator = tp + fn

    return tp / denominator if denominator > 0 else 0.0


def aucm_f1(counts: dict[str, int]) -> float:
    """
    Calculate the harmonic mean of AUCM precision and recall.

    F1 = 2 * precision * recall / (precision + recall)

    Returns 0.0 when precision + recall is zero.
    """
    precision = aucm_precision(counts)
    recall = aucm_recall(counts)

    denominator = precision + recall

    return (
        2 * precision * recall / denominator
        if denominator > 0
        else 0.0
    )


# =========================================================
# 3. ABSTENTION CONFUSION MATRIX
# =========================================================

def abstention_counts(
    gold_answerable: list[bool],
    predicted_abstain: list[bool],
) -> dict[str, int]:
    """
    Compute abstention confusion matrix counts.

    Positive class = Abstention.

    TP: Unanswerable question, model abstains.
    FP: Answerable question, model abstains.
    FN: Unanswerable question, model answers.
    TN: Answerable question, model answers.

    Args:
        gold_answerable: Whether each question is answerable.
        predicted_abstain: Whether the model abstained.

    Returns:
        Dictionary containing TP, FP, FN, and TN counts.

    Raises:
        ValueError: If input lists have different lengths.
    """
    if len(gold_answerable) != len(predicted_abstain):
        raise ValueError("Input lists must have equal lengths")

    counts = {
        "TP": 0,
        "FP": 0,
        "FN": 0,
        "TN": 0,
    }

    for gold, abstain in zip(
        gold_answerable,
        predicted_abstain,
        strict=True,
    ):
        if not gold and abstain:
            counts["TP"] += 1

        elif gold and abstain:
            counts["FP"] += 1

        elif not gold and not abstain:
            counts["FN"] += 1

        else:
            # Answerable question, model answers.
            counts["TN"] += 1

    return counts


# =========================================================
# 4. ABSTENTION PRECISION AND RECALL
# =========================================================

def abstention_precision(counts: dict[str, int]) -> float:
    """
    Calculate abstention precision.

    Precision = TP / (TP + FP)

    Measures how often the model's abstentions are justified.

    Returns 0.0 when the denominator is zero.
    """
    tp = counts["TP"]
    fp = counts["FP"]

    denominator = tp + fp

    return tp / denominator if denominator > 0 else 0.0


def abstention_recall(counts: dict[str, int]) -> float:
    """
    Calculate abstention recall.

    Recall = TP / (TP + FN)

    Measures how often the model abstains on
    unanswerable questions.

    Returns 0.0 when the denominator is zero.
    """
    tp = counts["TP"]
    fn = counts["FN"]

    denominator = tp + fn

    return tp / denominator if denominator > 0 else 0.0


# =========================================================
# 5. ANSWER NORMALIZATION
# =========================================================

def remove_articles_simple(text: str) -> str:
    """
    Remove standalone English articles: a, an, the.

    Preserves all other words.
    """
    articles = {"a", "an", "the"}

    words = [
        word
        for word in text.split()
        if word.lower() not in articles
    ]

    return " ".join(words)


def normalize_answer(text: str) -> list[str]:
    """
    Normalize an answer using SQuAD-style preprocessing.

    Steps:
        1. Convert text to lowercase.
        2. Remove ASCII punctuation.
        3. Remove articles (a, an, the).
        4. Split into whitespace-separated tokens.

    Returns:
        List of normalized word tokens.
    """
    # Step 1: Lowercase
    text = text.lower()

    # Step 2: Remove punctuation
    text = "".join(
        char
        for char in text
        if char not in string.punctuation
    )

    # Step 3: Remove articles
    text = remove_articles_simple(text)

    # Step 4: Tokenize
    return text.split()


# =========================================================
# 6. TOKEN-LEVEL F1
# =========================================================

def token_f1(
    prediction: str,
    reference: str,
) -> float:
    """
    Calculate word-level token F1 between a predicted
    answer and its reference answer.

    Steps:
        1. Normalize prediction and reference.
        2. Count overlapping tokens, including duplicates.
        3. Calculate F1 from the token overlap.

    Formula:
        F1 = 2 * matching_tokens /
             (predicted_tokens + reference_tokens)

    Returns:
        1.0 if both normalized answers are empty.
        0.0 if only one answer is empty.
        0.0 if the answers share no tokens.
        A value between 0.0 and 1.0 otherwise.
    """
    # Step 1: Normalize both answers
    prediction_tokens = normalize_answer(prediction)
    reference_tokens = normalize_answer(reference)

    # Step 2: Handle empty-answer cases
    if not prediction_tokens and not reference_tokens:
        return 1.0

    if not prediction_tokens or not reference_tokens:
        return 0.0

    # Step 3: Count occurrences of each token
    prediction_counts = Counter(prediction_tokens)
    reference_counts = Counter(reference_tokens)

    # Step 4: Count overlapping token occurrences
    common = prediction_counts & reference_counts
    num_common = sum(common.values())

    # Step 5: Calculate token-level F1
    return (
        2 * num_common
        / (len(prediction_tokens) + len(reference_tokens))
    )
