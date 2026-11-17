
import hashlib
from typing import Any

from src.data.schema import EvidenceExample


def adapt_squad_example(example: dict[str, Any]) -> EvidenceExample:
    """
    Convert a SQuAD 2.0 example into the EvidenceTune schema.

    Args:
        example: A single SQuAD 2.0 dataset record.

    Returns:
        A validated EvidenceExample.
    """

    # 1. Extract source fields
    example_id = example["id"]
    title = example["title"]
    context = example["context"]
    question = example["question"]
    answers = example["answers"]["text"]

    # 2. Determine answerability
    valid_answers = [
        answer.strip()
        for answer in answers
        if isinstance(answer, str) and answer.strip()
    ]

    is_answerable = len(valid_answers) > 0

    # 3. Convert the reference answer
    if is_answerable:
        reference_answer = valid_answers[0]
        category = "answerable"
    else:
        reference_answer = (
            "The provided context does not contain "
            "enough information to answer the question."
        )
        category = "unanswerable"

    # 4. Generate a stable source identifier
    # Group questions from the same article together.
    source_hash = hashlib.sha256(
        title.encode("utf-8")
    ).hexdigest()[:16]

    source_id = f"squad_v2:{source_hash}"

    # 5. Construct and validate the output
    return EvidenceExample(
        id=f"squad_v2:{example_id}",
        source_id=source_id,
        context=context,
        question=question,
        answer=reference_answer,
        answerable=is_answerable,
        category=category,
    )
