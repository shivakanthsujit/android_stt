package dev.localflow.dictation.cleanup

import java.text.Normalizer
import java.util.Locale

internal object CleanupGuardrails {
    fun sanitize(modelText: String): String {
        var candidate = modelText.trim()
        for (prefix in KNOWN_OUTPUT_PREFIXES) {
            if (candidate.startsWith(prefix, ignoreCase = true)) {
                candidate = candidate.substring(prefix.length).trim()
                break
            }
        }
        var removedSuffix: Boolean
        do {
            removedSuffix = false
            for (suffix in KNOWN_OUTPUT_SUFFIXES) {
                if (candidate.endsWith(suffix, ignoreCase = true)) {
                    candidate = candidate.dropLast(suffix.length).trim()
                    removedSuffix = true
                    break
                }
            }
        } while (removedSuffix)
        if (candidate.length >= 2 &&
            ((candidate.first() == '"' && candidate.last() == '"') ||
                (candidate.first() == '“' && candidate.last() == '”'))
        ) {
            candidate = candidate.substring(1, candidate.length - 1).trim()
        }
        return candidate
    }

    fun fallbackReason(
        rawText: String,
        candidate: String,
        hitOutputTokenLimit: Boolean,
    ): String? {
        when {
            candidate.isBlank() -> return "Model returned empty text"
            hitOutputTokenLimit -> return "Model reached the output token limit"
        }

        knownUnsafeResponseReason(rawText, candidate)?.let { return it }

        when {
            candidate.length * 10 < rawText.length * MIN_RETENTION_TENTHS ->
                return "Model output was suspiciously shorter than the input"
            candidate.length > rawText.length * MAX_EXPANSION_RATIO ->
                return "Model output exceeded the conservative expansion limit"
        }

        val rawTokens = tokenize(rawText)
        val candidateTokens = tokenize(candidate)
        if (rawTokens.isEmpty() || candidateTokens.isEmpty()) return null

        val rawWords = rawTokens.mapTo(mutableSetOf()) { it.normalized }
        val novelToken = candidateTokens.firstOrNull { token ->
            token.normalized !in rawWords && token.normalized !in ALLOWED_GRAMMAR_ADDITIONS
        }
        if (novelToken != null) {
            return "Model introduced new lexical content: ${novelToken.surface}"
        }

        val correction = findExplicitCorrection(rawTokens)
        val optionalRawIndices = buildSet {
            correction?.markerIndices?.let(::addAll)
            correction?.supersededTokenIndex?.let(::add)
        }
        val candidateWords = candidateTokens.mapTo(mutableSetOf()) { it.normalized }

        rawTokens.forEachIndexed { index, token ->
            if (index !in optionalRawIndices && isProtected(token, index)) {
                if (!candidateContainsProtectedToken(candidateTokens, token, index)) {
                    return "Model dropped protected lexical content: ${token.surface}"
                }
            }
        }

        correction?.let {
            val superseded = it.supersededTokenIndex?.let(rawTokens::get)
            val replacement = it.replacementTokenIndex?.let(rawTokens::get)
            if (it.replacementMustBeRetained &&
                replacement != null &&
                replacement.normalized !in candidateWords
            ) {
                return "Model did not preserve self-correction replacement"
            }
            if (superseded != null &&
                replacement != null &&
                superseded.normalized != replacement.normalized &&
                superseded.normalized in candidateWords &&
                replacement.normalized in candidateWords
            ) {
                return "Model retained superseded self-correction content"
            }
        }

        intentPreservationReason(rawTokens, candidateWords, optionalRawIndices)?.let { return it }
        return null
    }

    private const val MAX_EXPANSION_RATIO = 1.8
    private const val MIN_RETENTION_TENTHS = 3
    private const val MIN_INTENT_CONTENT_RETENTION_PERCENT = 65

    private data class LexicalToken(
        val surface: String,
        val normalized: String,
    )

    private data class CorrectionInfo(
        val markerIndices: Set<Int>,
        val supersededTokenIndex: Int?,
        val replacementTokenIndex: Int?,
        val replacementMustBeRetained: Boolean = false,
    )

    private enum class ProtectedKind {
        NEGATION,
        UNCERTAINTY,
        NUMBER,
        CAPITALIZED,
        TECHNICAL,
    }

    private fun knownUnsafeResponseReason(rawText: String, candidate: String): String? {
        val raw = rawText.trim().lowercase(Locale.ROOT)
        val output = candidate.trim().lowercase(Locale.ROOT)
        val metaPrefix = META_RESPONSE_PREFIXES.firstOrNull { prefix ->
            output.startsWith(prefix) && !raw.startsWith(prefix)
        }
        if (metaPrefix != null) return "Model summarized or described the dictation"

        val answerPrefix = ANSWER_RESPONSE_PREFIXES.firstOrNull { prefix ->
            val prefixWords = tokenize(prefix).map(LexicalToken::normalized)
            val rawWords = tokenize(rawText).map(LexicalToken::normalized)
            output.startsWith(prefix) && rawWords.take(prefixWords.size) != prefixWords
        }
        return if (answerPrefix == null) null else "Model answered or acted on the dictation"
    }

    private fun tokenize(text: String): List<LexicalToken> =
        NON_WHITESPACE.findAll(text).mapNotNull { match ->
            val surface = stripBoundaryPunctuation(match.value)
            if (surface.none(Char::isLetterOrDigit)) {
                null
            } else {
                LexicalToken(
                    surface = surface,
                    normalized = Normalizer.normalize(surface, Normalizer.Form.NFC)
                        .replace('’', '\'')
                        .lowercase(Locale.ROOT),
                )
            }
        }.toList()

    private fun stripBoundaryPunctuation(value: String): String {
        var start = 0
        var end = value.length
        while (start < end && value[start] in LEADING_BOUNDARY_PUNCTUATION) start += 1
        while (end > start && value[end - 1] in TRAILING_BOUNDARY_PUNCTUATION) end -= 1
        return value.substring(start, end)
    }

    private fun isProtected(token: LexicalToken, index: Int): Boolean =
        protectedKinds(token, index).isNotEmpty()

    private fun candidateContainsProtectedToken(
        candidateTokens: List<LexicalToken>,
        rawToken: LexicalToken,
        rawIndex: Int,
    ): Boolean {
        val kinds = protectedKinds(rawToken, rawIndex)
        return if (ProtectedKind.CAPITALIZED in kinds || ProtectedKind.TECHNICAL in kinds) {
            candidateTokens.any { candidate -> candidate.surface == rawToken.surface }
        } else {
            candidateTokens.any { candidate -> candidate.normalized == rawToken.normalized }
        }
    }

    private fun protectedKinds(token: LexicalToken, index: Int): Set<ProtectedKind> = buildSet {
        if (token.normalized in NEGATION_WORDS) add(ProtectedKind.NEGATION)
        if (token.normalized in UNCERTAINTY_WORDS) add(ProtectedKind.UNCERTAINTY)
        if (token.normalized.any(Char::isDigit) || token.normalized in NUMBER_WORDS) {
            add(ProtectedKind.NUMBER)
        }
        if (isCapitalizedContent(token, index)) add(ProtectedKind.CAPITALIZED)
        if (token.surface.any { character ->
                !character.isLetterOrDigit() && character != '\'' && character != '’'
            }
        ) {
            add(ProtectedKind.TECHNICAL)
        }
    }

    private fun isCapitalizedContent(token: LexicalToken, index: Int): Boolean {
        if (token.normalized in FILLER_WORDS) return false
        val letters = token.surface.filter(Char::isLetter)
        if (letters.isEmpty()) return false
        val acronym = letters.length >= 2 && letters.all(Char::isUpperCase)
        val startsUppercase = token.surface.firstOrNull(Char::isLetter)?.isUpperCase() == true
        return acronym || startsUppercase || (index > 0 && letters.any(Char::isUpperCase))
    }

    private fun findExplicitCorrection(tokens: List<LexicalToken>): CorrectionInfo? {
        for (markerStart in tokens.indices.reversed()) {
            val markerEnd: Int
            val unconditionallyExplicit: Boolean
            when {
                tokens[markerStart].normalized == "actually" &&
                    tokens.getOrNull(markerStart + 1)?.normalized == "make" &&
                    tokens.getOrNull(markerStart + 2)?.normalized == "that" -> {
                    markerEnd = markerStart + 2
                    unconditionallyExplicit = true
                }
                tokens[markerStart].normalized == "actually" &&
                    tokens.getOrNull(markerStart + 1)?.normalized == "no" -> {
                    markerEnd = markerStart + 1
                    unconditionallyExplicit = true
                }
                tokens[markerStart].normalized == "make" &&
                    tokens.getOrNull(markerStart + 1)?.normalized == "that" -> {
                    markerEnd = markerStart + 1
                    unconditionallyExplicit = true
                }
                tokens[markerStart].normalized == "actually" -> {
                    markerEnd = markerStart
                    unconditionallyExplicit = false
                }
                else -> continue
            }

            val before = (markerStart - 1 downTo 0).firstOrNull { index ->
                isProtected(tokens[index], index)
            }
            val after = (markerEnd + 1 until tokens.size).firstOrNull { index ->
                isProtected(tokens[index], index)
            }
            val matchingProtectedKind = before != null && after != null &&
                protectedKinds(tokens[before], before)
                    .intersect(protectedKinds(tokens[after], after))
                    .isNotEmpty()
            val imperativeCorrection = if (!unconditionallyExplicit && !matchingProtectedKind) {
                findBareActuallyImperativeCorrection(tokens, markerStart, markerEnd)
            } else {
                null
            }
            if (!unconditionallyExplicit && !matchingProtectedKind && imperativeCorrection == null) {
                continue
            }

            return CorrectionInfo(
                markerIndices = (markerStart..markerEnd).toSet(),
                supersededTokenIndex = imperativeCorrection?.first ?: before,
                replacementTokenIndex = imperativeCorrection?.second ?: after,
                replacementMustBeRetained = imperativeCorrection != null,
            )
        }
        return null
    }

    /**
     * Recognize a narrow form of bare-"actually" correction that has no protected
     * name or number to anchor it: both clauses must begin with known imperative
     * verbs and must share a content word (for example, "archive the draft actually
     * keep the draft"). The shared-object requirement avoids treating unrelated
     * consecutive commands as a correction.
     */
    private fun findBareActuallyImperativeCorrection(
        tokens: List<LexicalToken>,
        markerStart: Int,
        markerEnd: Int,
    ): Pair<Int, Int>? {
        if (markerStart != markerEnd || tokens[markerStart].normalized != "actually") return null

        val ignorableClausePrefix = FILLER_WORDS + INTENT_LEADING_WORDS
        val beforeVerb = (0 until markerStart).firstOrNull { index ->
            tokens[index].normalized !in ignorableClausePrefix
        } ?: return null
        val afterVerb = (markerEnd + 1 until tokens.size).firstOrNull { index ->
            tokens[index].normalized !in ignorableClausePrefix
        } ?: return null
        if (tokens[beforeVerb].normalized !in IMPERATIVE_CORRECTION_WORDS ||
            tokens[afterVerb].normalized !in IMPERATIVE_CORRECTION_WORDS
        ) {
            return null
        }

        fun contentWords(indices: IntRange): Set<String> = indices.asSequence()
            .map { tokens[it].normalized }
            .filterNot(FILLER_WORDS::contains)
            .filterNot(INTENT_LEADING_WORDS::contains)
            .filterNot(ALLOWED_GRAMMAR_ADDITIONS::contains)
            .toSet()

        val beforeContent = contentWords((beforeVerb + 1) until markerStart)
        val afterContent = contentWords((afterVerb + 1) until tokens.size)
        if (beforeContent.intersect(afterContent).isEmpty()) return null
        return beforeVerb to afterVerb
    }

    private fun intentPreservationReason(
        rawTokens: List<LexicalToken>,
        candidateWords: Set<String>,
        optionalRawIndices: Set<Int>,
    ): String? {
        val meaningfulRawIndices = rawTokens.indices.filter { index ->
            rawTokens[index].normalized !in FILLER_WORDS
        }
        if (meaningfulRawIndices.isEmpty()) return null

        val firstIndex = meaningfulRawIndices.first()
        val firstWord = rawTokens[firstIndex].normalized
        val intentIndex = when {
            firstWord in QUESTION_OR_COMMAND_WORDS -> firstIndex
            firstWord in INTENT_LEADING_WORDS -> meaningfulRawIndices.drop(1)
                .firstOrNull { rawTokens[it].normalized in QUESTION_OR_COMMAND_WORDS }
            else -> null
        } ?: return null
        val intentWord = rawTokens[intentIndex].normalized
        if (intentWord !in candidateWords) return "Model did not preserve the dictated intent"

        val requiredContent = rawTokens.indices.asSequence()
            .filterNot(optionalRawIndices::contains)
            .map { rawTokens[it].normalized }
            .filterNot(FILLER_WORDS::contains)
            .filterNot(ALLOWED_GRAMMAR_ADDITIONS::contains)
            .toSet()
        if (requiredContent.size <= 1) return null
        val retained = requiredContent.count(candidateWords::contains)
        if (retained * 100 < requiredContent.size * MIN_INTENT_CONTENT_RETENTION_PERCENT) {
            return "Model removed too much question or command content"
        }
        return null
    }

    private val NON_WHITESPACE = Regex("""\S+""")
    private val LEADING_BOUNDARY_PUNCTUATION = setOf('"', '\'', '“', '”', '(', '[', '{', ',', ';', '!', '?')
    private val TRAILING_BOUNDARY_PUNCTUATION =
        setOf('"', '\'', '“', '”', ')', ']', '}', ',', ';', '!', '?', '.')

    private val FILLER_WORDS = setOf("uh", "um", "er", "erm")
    private val NEGATION_WORDS = setOf(
        "no", "not", "never", "neither", "nor", "without", "unless", "cannot", "can't",
        "don't", "doesn't", "didn't", "won't", "wouldn't", "shouldn't", "isn't", "aren't",
    )
    private val UNCERTAINTY_WORDS = setOf(
        "think", "believe", "maybe", "perhaps", "probably", "possibly", "uncertain", "unsure",
        "seems", "seem", "guess", "roughly", "approximately",
    )
    private val NUMBER_WORDS = setOf(
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
        "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
        "hundred", "thousand", "million", "billion", "first", "second", "third", "fourth", "fifth",
        "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
    )
    private val ALLOWED_GRAMMAR_ADDITIONS = setOf(
        "a", "an", "the", "and", "or", "but", "that", "this", "it", "is", "are", "was", "were",
        "be", "been", "being", "to", "of", "for", "on", "in", "at", "by", "with", "then",
    )
    private val QUESTION_OR_COMMAND_WORDS = setOf(
        "what", "when", "where", "why", "how", "who", "which", "can", "could", "would", "will",
        "should", "do", "does", "did", "are", "is", "send", "write", "explain", "run", "set",
        "remind", "call", "install", "turn", "record", "open", "close", "create", "delete", "make",
        "schedule", "tell", "show", "list", "draft", "email", "text", "output",
    )
    private val IMPERATIVE_CORRECTION_WORDS = setOf(
        "send", "write", "explain", "run", "set", "remind", "call", "install", "turn",
        "record", "open", "close", "create", "delete", "make", "schedule", "tell", "show",
        "list", "draft", "email", "text", "output", "archive", "keep",
    )
    private val INTENT_LEADING_WORDS = setOf("please", "first", "next", "then")

    private val META_RESPONSE_PREFIXES = listOf(
        "the speaker ", "the transcript ", "this transcript ", "the user ", "it sounds like ",
        "the task is ",
    )
    private val ANSWER_RESPONSE_PREFIXES = listOf(
        "sure,", "certainly", "of course", "i can help", "i'll make sure", "i will make sure",
        "please wait while", "here is", "here's",
    )

    private val KNOWN_OUTPUT_PREFIXES = listOf(
        "The cleaned transcript is:",
        "Cleaned transcript:",
        "The cleaned text is:",
        "Cleaned text:",
        "The corrected text is:",
        "Corrected text:",
    )
    private val KNOWN_OUTPUT_SUFFIXES = listOf(
        "END QUOTED TEXT",
        "EDIT:",
        "</dictation>",
        "</transcript_data>",
    )
}
