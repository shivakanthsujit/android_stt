"""Host-side port of Android's ``CleanupGuardrails``.

Keep this module behaviorally aligned with
``app/src/main/java/dev/localflow/dictation/cleanup/CleanupGuardrails.kt`` so
host model evaluations select the same fallback text as the Android harness.
It intentionally uses only the Python standard library.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum, auto


MIN_RETENTION_TENTHS = 3
MAX_EXPANSION_RATIO = 1.8
MIN_INTENT_CONTENT_RETENTION_PERCENT = 65

LEADING_BOUNDARY_PUNCTUATION = frozenset('"\'“”([{,;!?')
TRAILING_BOUNDARY_PUNCTUATION = frozenset('"\'“”)]},;!?.')

FILLER_WORDS = frozenset(("uh", "um", "er", "erm"))
NEGATION_WORDS = frozenset(
    (
        "no",
        "not",
        "never",
        "neither",
        "nor",
        "without",
        "unless",
        "cannot",
        "can't",
        "don't",
        "doesn't",
        "didn't",
        "won't",
        "wouldn't",
        "shouldn't",
        "isn't",
        "aren't",
    )
)
UNCERTAINTY_WORDS = frozenset(
    (
        "think",
        "believe",
        "maybe",
        "perhaps",
        "probably",
        "possibly",
        "uncertain",
        "unsure",
        "seems",
        "seem",
        "guess",
        "roughly",
        "approximately",
    )
)
NUMBER_WORDS = frozenset(
    (
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "million",
        "billion",
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
    )
)
ALLOWED_GRAMMAR_ADDITIONS = frozenset(
    (
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "that",
        "this",
        "it",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "to",
        "of",
        "for",
        "on",
        "in",
        "at",
        "by",
        "with",
        "then",
    )
)
QUESTION_OR_COMMAND_WORDS = frozenset(
    (
        "what",
        "when",
        "where",
        "why",
        "how",
        "who",
        "which",
        "can",
        "could",
        "would",
        "will",
        "should",
        "do",
        "does",
        "did",
        "are",
        "is",
        "send",
        "write",
        "explain",
        "run",
        "set",
        "remind",
        "call",
        "install",
        "turn",
        "record",
        "open",
        "close",
        "create",
        "delete",
        "make",
        "schedule",
        "tell",
        "show",
        "list",
        "draft",
        "email",
        "text",
        "output",
    )
)
IMPERATIVE_CORRECTION_WORDS = frozenset(
    (
        "send",
        "write",
        "explain",
        "run",
        "set",
        "remind",
        "call",
        "install",
        "turn",
        "record",
        "open",
        "close",
        "create",
        "delete",
        "make",
        "schedule",
        "tell",
        "show",
        "list",
        "draft",
        "email",
        "text",
        "output",
        "archive",
        "keep",
    )
)
INTENT_LEADING_WORDS = frozenset(("please", "first", "next", "then"))

META_RESPONSE_PREFIXES = (
    "the speaker ",
    "the transcript ",
    "this transcript ",
    "the user ",
    "it sounds like ",
    "the task is ",
)
ANSWER_RESPONSE_PREFIXES = (
    "sure,",
    "certainly",
    "of course",
    "i can help",
    "i'll make sure",
    "i will make sure",
    "please wait while",
    "here is",
    "here's",
)
KNOWN_OUTPUT_PREFIXES = (
    "The cleaned transcript is:",
    "Cleaned transcript:",
    "The cleaned text is:",
    "Cleaned text:",
    "The corrected text is:",
    "Corrected text:",
)
KNOWN_OUTPUT_SUFFIXES = (
    "END QUOTED TEXT",
    "EDIT:",
    "</dictation>",
    "</transcript_data>",
)


@dataclass(frozen=True)
class LexicalToken:
    surface: str
    normalized: str


@dataclass(frozen=True)
class CorrectionInfo:
    marker_indices: frozenset[int]
    superseded_token_index: int | None
    replacement_token_index: int | None
    replacement_must_be_retained: bool = False


class ProtectedKind(Enum):
    NEGATION = auto()
    UNCERTAINTY = auto()
    NUMBER = auto()
    CAPITALIZED = auto()
    TECHNICAL = auto()


def _is_digit(character: str) -> bool:
    """Match Java/Kotlin ``Char.isDigit`` rather than Python's broader isdigit."""

    return unicodedata.category(character) == "Nd"


def _is_letter_or_digit(character: str) -> bool:
    return character.isalpha() or _is_digit(character)


def sanitize(model_text: str) -> str:
    """Strip only wrappers recognized by the Android cleanup harness."""

    candidate = model_text.strip()
    lowered = candidate.lower()
    for prefix in KNOWN_OUTPUT_PREFIXES:
        if lowered.startswith(prefix.lower()):
            candidate = candidate[len(prefix) :].strip()
            break

    while True:
        lowered = candidate.lower()
        for suffix in KNOWN_OUTPUT_SUFFIXES:
            if lowered.endswith(suffix.lower()):
                candidate = candidate[: -len(suffix)].strip()
                break
        else:
            break

    if len(candidate) >= 2 and (
        (candidate[0] == '"' and candidate[-1] == '"')
        or (candidate[0] == "“" and candidate[-1] == "”")
    ):
        candidate = candidate[1:-1].strip()
    return candidate


def _strip_boundary_punctuation(value: str) -> str:
    start = 0
    end = len(value)
    while start < end and value[start] in LEADING_BOUNDARY_PUNCTUATION:
        start += 1
    while end > start and value[end - 1] in TRAILING_BOUNDARY_PUNCTUATION:
        end -= 1
    return value[start:end]


def tokenize(text: str) -> list[LexicalToken]:
    tokens: list[LexicalToken] = []
    for match in re.finditer(r"\S+", text):
        surface = _strip_boundary_punctuation(match.group(0))
        if not any(_is_letter_or_digit(character) for character in surface):
            continue
        tokens.append(
            LexicalToken(
                surface=surface,
                normalized=unicodedata.normalize("NFC", surface)
                .replace("’", "'")
                .lower(),
            )
        )
    return tokens


def _is_capitalized_content(token: LexicalToken, index: int) -> bool:
    if token.normalized in FILLER_WORDS:
        return False
    letters = [character for character in token.surface if character.isalpha()]
    if not letters:
        return False
    acronym = len(letters) >= 2 and all(character.isupper() for character in letters)
    first_letter = next(
        (character for character in token.surface if character.isalpha()), None
    )
    starts_uppercase = first_letter is not None and first_letter.isupper()
    return acronym or starts_uppercase or (
        index > 0 and any(character.isupper() for character in letters)
    )


def _protected_kinds(token: LexicalToken, index: int) -> frozenset[ProtectedKind]:
    kinds: set[ProtectedKind] = set()
    if token.normalized in NEGATION_WORDS:
        kinds.add(ProtectedKind.NEGATION)
    if token.normalized in UNCERTAINTY_WORDS:
        kinds.add(ProtectedKind.UNCERTAINTY)
    if any(_is_digit(character) for character in token.normalized) or (
        token.normalized in NUMBER_WORDS
    ):
        kinds.add(ProtectedKind.NUMBER)
    if _is_capitalized_content(token, index):
        kinds.add(ProtectedKind.CAPITALIZED)
    if any(
        not _is_letter_or_digit(character) and character not in ("'", "’")
        for character in token.surface
    ):
        kinds.add(ProtectedKind.TECHNICAL)
    return frozenset(kinds)


def _is_protected(token: LexicalToken, index: int) -> bool:
    return bool(_protected_kinds(token, index))


def _candidate_contains_protected_token(
    candidate_tokens: list[LexicalToken], raw_token: LexicalToken, raw_index: int
) -> bool:
    kinds = _protected_kinds(raw_token, raw_index)
    if ProtectedKind.CAPITALIZED in kinds or ProtectedKind.TECHNICAL in kinds:
        return any(candidate.surface == raw_token.surface for candidate in candidate_tokens)
    return any(
        candidate.normalized == raw_token.normalized for candidate in candidate_tokens
    )


def _known_unsafe_response_reason(raw_text: str, candidate: str) -> str | None:
    raw = raw_text.strip().lower()
    output = candidate.strip().lower()
    if any(output.startswith(prefix) and not raw.startswith(prefix) for prefix in META_RESPONSE_PREFIXES):
        return "Model summarized or described the dictation"

    raw_words = [token.normalized for token in tokenize(raw_text)]
    for prefix in ANSWER_RESPONSE_PREFIXES:
        prefix_words = [token.normalized for token in tokenize(prefix)]
        if output.startswith(prefix) and raw_words[: len(prefix_words)] != prefix_words:
            return "Model answered or acted on the dictation"
    return None


def _find_explicit_correction(tokens: list[LexicalToken]) -> CorrectionInfo | None:
    for marker_start in range(len(tokens) - 1, -1, -1):
        marker_end: int
        unconditionally_explicit: bool
        if (
            tokens[marker_start].normalized == "actually"
            and marker_start + 2 < len(tokens)
            and tokens[marker_start + 1].normalized == "make"
            and tokens[marker_start + 2].normalized == "that"
        ):
            marker_end = marker_start + 2
            unconditionally_explicit = True
        elif (
            tokens[marker_start].normalized == "actually"
            and marker_start + 1 < len(tokens)
            and tokens[marker_start + 1].normalized == "no"
        ):
            marker_end = marker_start + 1
            unconditionally_explicit = True
        elif (
            tokens[marker_start].normalized == "make"
            and marker_start + 1 < len(tokens)
            and tokens[marker_start + 1].normalized == "that"
        ):
            marker_end = marker_start + 1
            unconditionally_explicit = True
        elif tokens[marker_start].normalized == "actually":
            marker_end = marker_start
            unconditionally_explicit = False
        else:
            continue

        before = next(
            (
                index
                for index in range(marker_start - 1, -1, -1)
                if _is_protected(tokens[index], index)
            ),
            None,
        )
        after = next(
            (
                index
                for index in range(marker_end + 1, len(tokens))
                if _is_protected(tokens[index], index)
            ),
            None,
        )
        matching_protected_kind = (
            before is not None
            and after is not None
            and bool(
                _protected_kinds(tokens[before], before).intersection(
                    _protected_kinds(tokens[after], after)
                )
            )
        )
        imperative_correction = (
            _find_bare_actually_imperative_correction(tokens, marker_start, marker_end)
            if not unconditionally_explicit and not matching_protected_kind
            else None
        )
        if (
            not unconditionally_explicit
            and not matching_protected_kind
            and imperative_correction is None
        ):
            continue
        return CorrectionInfo(
            marker_indices=frozenset(range(marker_start, marker_end + 1)),
            superseded_token_index=(
                imperative_correction[0] if imperative_correction is not None else before
            ),
            replacement_token_index=(
                imperative_correction[1] if imperative_correction is not None else after
            ),
            replacement_must_be_retained=imperative_correction is not None,
        )
    return None


def _find_bare_actually_imperative_correction(
    tokens: list[LexicalToken], marker_start: int, marker_end: int
) -> tuple[int, int] | None:
    """Recognize only imperative rewrites that retain a shared content object."""

    if marker_start != marker_end or tokens[marker_start].normalized != "actually":
        return None

    ignorable_clause_prefix = FILLER_WORDS | INTENT_LEADING_WORDS
    before_verb = next(
        (
            index
            for index in range(marker_start)
            if tokens[index].normalized not in ignorable_clause_prefix
        ),
        None,
    )
    after_verb = next(
        (
            index
            for index in range(marker_end + 1, len(tokens))
            if tokens[index].normalized not in ignorable_clause_prefix
        ),
        None,
    )
    if before_verb is None or after_verb is None:
        return None
    if (
        tokens[before_verb].normalized not in IMPERATIVE_CORRECTION_WORDS
        or tokens[after_verb].normalized not in IMPERATIVE_CORRECTION_WORDS
    ):
        return None

    excluded_content_words = (
        FILLER_WORDS | INTENT_LEADING_WORDS | ALLOWED_GRAMMAR_ADDITIONS
    )
    before_content = {
        tokens[index].normalized
        for index in range(before_verb + 1, marker_start)
        if tokens[index].normalized not in excluded_content_words
    }
    after_content = {
        tokens[index].normalized
        for index in range(after_verb + 1, len(tokens))
        if tokens[index].normalized not in excluded_content_words
    }
    if before_content.isdisjoint(after_content):
        return None
    return before_verb, after_verb


def _intent_preservation_reason(
    raw_tokens: list[LexicalToken],
    candidate_words: set[str],
    optional_raw_indices: set[int],
) -> str | None:
    meaningful_raw_indices = [
        index
        for index, token in enumerate(raw_tokens)
        if token.normalized not in FILLER_WORDS
    ]
    if not meaningful_raw_indices:
        return None

    first_index = meaningful_raw_indices[0]
    first_word = raw_tokens[first_index].normalized
    if first_word in QUESTION_OR_COMMAND_WORDS:
        intent_index = first_index
    elif first_word in INTENT_LEADING_WORDS:
        intent_index = next(
            (
                index
                for index in meaningful_raw_indices[1:]
                if raw_tokens[index].normalized in QUESTION_OR_COMMAND_WORDS
            ),
            None,
        )
    else:
        intent_index = None
    if intent_index is None:
        return None

    intent_word = raw_tokens[intent_index].normalized
    if intent_word not in candidate_words:
        return "Model did not preserve the dictated intent"

    required_content = {
        token.normalized
        for index, token in enumerate(raw_tokens)
        if index not in optional_raw_indices
        and token.normalized not in FILLER_WORDS
        and token.normalized not in ALLOWED_GRAMMAR_ADDITIONS
    }
    if len(required_content) <= 1:
        return None
    retained = sum(word in candidate_words for word in required_content)
    if retained * 100 < len(required_content) * MIN_INTENT_CONTENT_RETENTION_PERCENT:
        return "Model removed too much question or command content"
    return None


def _kotlin_string_length(text: str) -> int:
    """Return Kotlin/JVM ``String.length`` (UTF-16 code units)."""

    return len(text.encode("utf-16-le", errors="surrogatepass")) // 2


def fallback_reason(
    raw_text: str, candidate: str, hit_output_token_limit: bool
) -> str | None:
    """Return Android's rejection reason, or ``None`` when the edit is accepted."""

    if not candidate or candidate.isspace():
        return "Model returned empty text"
    if hit_output_token_limit:
        return "Model reached the output token limit"

    unsafe_reason = _known_unsafe_response_reason(raw_text, candidate)
    if unsafe_reason is not None:
        return unsafe_reason

    raw_length = _kotlin_string_length(raw_text)
    candidate_length = _kotlin_string_length(candidate)
    if candidate_length * 10 < raw_length * MIN_RETENTION_TENTHS:
        return "Model output was suspiciously shorter than the input"
    if candidate_length > raw_length * MAX_EXPANSION_RATIO:
        return "Model output exceeded the conservative expansion limit"

    raw_tokens = tokenize(raw_text)
    candidate_tokens = tokenize(candidate)
    if not raw_tokens or not candidate_tokens:
        return None

    raw_words = {token.normalized for token in raw_tokens}
    novel_token = next(
        (
            token
            for token in candidate_tokens
            if token.normalized not in raw_words
            and token.normalized not in ALLOWED_GRAMMAR_ADDITIONS
        ),
        None,
    )
    if novel_token is not None:
        return f"Model introduced new lexical content: {novel_token.surface}"

    correction = _find_explicit_correction(raw_tokens)
    optional_raw_indices: set[int] = set()
    if correction is not None:
        optional_raw_indices.update(correction.marker_indices)
        if correction.superseded_token_index is not None:
            optional_raw_indices.add(correction.superseded_token_index)
    candidate_words = {token.normalized for token in candidate_tokens}

    for index, token in enumerate(raw_tokens):
        if index not in optional_raw_indices and _is_protected(token, index):
            if not _candidate_contains_protected_token(candidate_tokens, token, index):
                return f"Model dropped protected lexical content: {token.surface}"

    if correction is not None:
        superseded = (
            raw_tokens[correction.superseded_token_index]
            if correction.superseded_token_index is not None
            else None
        )
        replacement = (
            raw_tokens[correction.replacement_token_index]
            if correction.replacement_token_index is not None
            else None
        )
        if (
            correction.replacement_must_be_retained
            and replacement is not None
            and replacement.normalized not in candidate_words
        ):
            return "Model did not preserve self-correction replacement"
        if (
            superseded is not None
            and replacement is not None
            and superseded.normalized != replacement.normalized
            and superseded.normalized in candidate_words
            and replacement.normalized in candidate_words
        ):
            return "Model retained superseded self-correction content"

    return _intent_preservation_reason(
        raw_tokens, candidate_words, optional_raw_indices
    )
