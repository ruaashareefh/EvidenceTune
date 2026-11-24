"""Strict extraction of the pinned Lavi et al. abstain-aware development format."""

import hashlib
import re

from src.data.schema import EvidenceExample

SOURCE_REVISION = '9ea9afbd2aa02052c7b3ee4995aa5f26e9b6cd2f'
PREFIX = ('Given the following passage and question, answer the question.\n'
          ' First make sure if it can be answered by the passage.\n'
          '         If it cannot be answered based on the passage, reply "unanswerable" \n'
          '         Passage: ')
QUESTION_SEPARATOR = ' \n         Question: '
SUFFIX = ' \n         Answer: '
UNANSWERABLE_REFERENCE = 'The answer is not found in the document.'


def adapt_record(row, source_path, row_index):
    """Use filename labels and occurrence IDs; never infer unavailable article IDs.

    Exact template boundaries are removed; passage, question, and gt_answer bytes
    within the decoded JSON strings are otherwise preserved. Duplicate rows get
    distinct occurrence IDs and are reported by the ingestion audit, not dropped.
    """
    match = re.fullmatch(r'data/abstain_aware_prompt/(squad|repliqa)/(answerable|unanswerable)_val\.json', source_path)
    if match is None:
        raise ValueError(f'Unsupported development source path: {source_path}')
    if type(row_index) is not int or row_index < 0:
        raise ValueError('row_index must be a nonnegative integer')
    if not isinstance(row, dict):
        raise ValueError('Source record must be an object')
    instruction, answer = row.get('instruction'), row.get('gt_answer')
    if not isinstance(instruction, str) or not instruction.startswith(PREFIX) or not instruction.endswith(SUFFIX):
        raise ValueError(f'{source_path}:{row_index}: unexpected instruction template')
    body = instruction[len(PREFIX):-len(SUFFIX)]
    if body.count(QUESTION_SEPARATOR) != 1 or SUFFIX in body or PREFIX in body:
        raise ValueError(f'{source_path}:{row_index}: ambiguous passage/question boundaries')
    context, question = body.split(QUESTION_SEPARATOR)
    if not context.strip() or not question.strip():
        raise ValueError(f'{source_path}:{row_index}: empty passage or question')
    dataset, category = match.groups()
    answerable = category == 'answerable'
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError(f'{source_path}:{row_index}: invalid gt_answer')
    if (not answerable and answer != UNANSWERABLE_REFERENCE) or (
            answerable and answer.strip().casefold() == UNANSWERABLE_REFERENCE.casefold()):
        raise ValueError(f'{source_path}:{row_index}: filename/gt_answer disagreement')
    return EvidenceExample(
        id=f'lavi2026:{SOURCE_REVISION[:12]}:{dataset}:val:{category}:{row_index:06d}',
        source_id='lavi2026:passage_sha256:' + hashlib.sha256(context.encode('utf-8')).hexdigest(),
        context=context, question=question, answer=answer,
        answerable=answerable, category=category,
    )
