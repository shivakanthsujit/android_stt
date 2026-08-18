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
            token.normalized !in rawWords &&
                token.normalized !in ALLOWED_GRAMMAR_ADDITIONS &&
                !isEquivalentNumericCandidate(token, rawTokens)
        }
        if (novelToken != null) {
            return "Model introduced new lexical content: ${novelToken.surface}"
        }

        val correction = findExplicitCorrection(rawTokens)
        val optionalRawIndices = buildSet {
            correction?.markerIndices?.let(::addAll)
            correction?.supersededTokenIndices?.let(::addAll)
            addAll(formattingDirectiveIndices(rawTokens))
            addAll(abandonedLeadInIndices(rawTokens))
        }
        val candidateWords = candidateTokens.mapTo(mutableSetOf()) { it.normalized }

        rawTokens.forEachIndexed { index, token ->
            if (index !in optionalRawIndices && isProtected(token, index)) {
                if (!candidateContainsProtectedToken(candidateTokens, token, index, rawTokens)) {
                    return "Model dropped protected lexical content: ${token.surface}"
                }
            }
        }

        correction?.let {
            val supersededIndex = it.supersededComparisonTokenIndex
            val superseded = supersededIndex?.let(rawTokens::get)
            val replacement = it.replacementTokenIndex?.let(rawTokens::get)
            if (it.replacementMustBeRetained &&
                replacement != null &&
                !candidateContainsProtectedToken(
                    candidateTokens,
                    replacement,
                    it.replacementTokenIndex,
                    rawTokens,
                )
            ) {
                return "Model did not preserve self-correction replacement"
            }
            if (superseded != null &&
                replacement != null &&
                superseded.normalized != replacement.normalized &&
                candidateContainsProtectedToken(
                    candidateTokens,
                    superseded,
                    supersededIndex,
                    rawTokens,
                ) &&
                candidateContainsProtectedToken(
                    candidateTokens,
                    replacement,
                    it.replacementTokenIndex,
                    rawTokens,
                )
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
        val supersededTokenIndices: Set<Int>,
        val supersededComparisonTokenIndex: Int?,
        val replacementTokenIndex: Int?,
        val replacementMustBeRetained: Boolean = false,
    )

    private data class NumberSpan(
        val indices: IntRange,
        val canonicalForms: Set<String>,
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
        rawTokens: List<LexicalToken>? = null,
    ): Boolean {
        val kinds = protectedKinds(rawToken, rawIndex)
        if (ProtectedKind.NUMBER in kinds && rawTokens != null) {
            val rawNumber = numberSpanContaining(rawTokens, rawIndex)
            if (rawNumber != null && candidateTokens.any { candidate ->
                    numericDigits(candidate)?.let(rawNumber.canonicalForms::contains) == true
                }
            ) {
                return true
            }
        }
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

    private fun isEquivalentNumericCandidate(
        candidate: LexicalToken,
        rawTokens: List<LexicalToken>,
    ): Boolean {
        val digits = numericDigits(candidate) ?: return false
        return numberSpans(rawTokens).any { digits in it.canonicalForms }
    }

    private fun numericDigits(token: LexicalToken): String? {
        if (token.surface.none(Char::isDigit) || token.surface.any(Char::isLetter)) return null
        return token.surface.filter(Char::isDigit).ifEmpty { null }
    }

    private fun numberSpanContaining(tokens: List<LexicalToken>, index: Int): NumberSpan? =
        numberSpans(tokens).firstOrNull { index in it.indices }

    private fun numberSpans(tokens: List<LexicalToken>): List<NumberSpan> {
        val spans = mutableListOf<NumberSpan>()
        var start = 0
        while (start < tokens.size) {
            if (tokens[start].normalized !in NUMBER_WORDS) {
                start += 1
                continue
            }
            var end = start
            while (end + 1 < tokens.size && tokens[end + 1].normalized in NUMBER_WORDS) end += 1
            val words = (start..end).map { tokens[it].normalized }
            val canonical = canonicalNumberForms(
                words = words,
                hasRecentTimeCue = tokens
                    .subList(maxOf(0, start - TIME_CUE_LOOKBACK_TOKENS), start)
                    .any { it.normalized in TIME_CUE_WORDS },
                followingWord = tokens.getOrNull(end + 1)?.normalized,
            )
            if (canonical.isNotEmpty()) spans += NumberSpan(start..end, canonical)
            start = end + 1
        }
        return spans
    }

    private fun canonicalNumberForms(
        words: List<String>,
        hasRecentTimeCue: Boolean,
        followingWord: String?,
    ): Set<String> {
        val values = words.mapNotNull(NUMBER_WORD_VALUES::get)
        if (values.size != words.size) return emptySet()

        val isSpokenTime = words.size == 2 &&
            values[0] in 1..12 &&
            values[1] in 0..59 &&
            (hasRecentTimeCue || followingWord in TIME_SUFFIX_WORDS)
        if (isSpokenTime) {
            return setOf(values[0].toString() + values[1].toString().padStart(2, '0'))
        }

        val isDigitSequence = words.size >= 3 && words.all(SINGLE_DIGIT_WORDS::contains)
        if (isDigitSequence) {
            return setOf(values.joinToString(separator = ""))
        }

        val parsed = parseCardinalNumber(words) ?: return emptySet()
        return setOf(parsed.toString())
    }

    private fun parseCardinalNumber(words: List<String>): Long? {
        var total = 0L
        var current = 0L
        for (word in words) {
            val value = NUMBER_WORD_VALUES[word]?.toLong() ?: return null
            when (word) {
                "hundred" -> current = maxOf(1L, current) * 100L
                "thousand" -> {
                    total += maxOf(1L, current) * 1_000L
                    current = 0L
                }
                "million" -> {
                    total += maxOf(1L, current) * 1_000_000L
                    current = 0L
                }
                "billion" -> {
                    total += maxOf(1L, current) * 1_000_000_000L
                    current = 0L
                }
                else -> current += value
            }
        }
        return total + current
    }

    private fun isCapitalizedContent(token: LexicalToken, index: Int): Boolean {
        if (token.normalized in FILLER_WORDS || token.normalized in REMOVABLE_DISCOURSE_WORDS) {
            return false
        }
        val letters = token.surface.filter(Char::isLetter)
        if (letters.isEmpty()) return false
        val acronym = letters.length >= 2 && letters.all(Char::isUpperCase)
        val startsUppercase = token.surface.firstOrNull(Char::isLetter)?.isUpperCase() == true
        return acronym || startsUppercase || (index > 0 && letters.any(Char::isUpperCase))
    }

    private fun findExplicitCorrection(tokens: List<LexicalToken>): CorrectionInfo? {
        for (markerStart in tokens.indices.reversed()) {
            if (tokens[markerStart].normalized == "sorry") {
                findSorryImperativeCorrection(tokens, markerStart)?.let { return it }
            }
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
                supersededTokenIndices = setOfNotNull(imperativeCorrection?.first ?: before),
                supersededComparisonTokenIndex = imperativeCorrection?.first ?: before,
                replacementTokenIndex = imperativeCorrection?.second ?: after,
                replacementMustBeRetained = imperativeCorrection != null,
            )
        }
        return null
    }

    private fun formattingDirectiveIndices(tokens: List<LexicalToken>): Set<Int> = buildSet {
        if (tokens.size >= 4 &&
            tokens[0].normalized in setOf("make", "start") &&
            tokens[1].normalized == "a" &&
            tokens[2].normalized in setOf("bullet", "bulleted", "numbered") &&
            tokens[3].normalized == "list"
        ) {
            addAll(0..3)
        }
        for (index in 0 until tokens.lastIndex) {
            if (tokens[index].normalized == "new" &&
                tokens[index + 1].normalized == "paragraph"
            ) {
                add(index)
                add(index + 1)
            }
        }
    }

    private fun abandonedLeadInIndices(tokens: List<LexicalToken>): Set<Int> {
        val words = tokens.map(LexicalToken::normalized)
        val exactLeadIn = listOf("i", "was", "going", "to", "i", "wanted", "to", "write", "that")
        return if (words.take(exactLeadIn.size) == exactLeadIn) {
            exactLeadIn.indices.toSet()
        } else {
            emptySet()
        }
    }

    private fun findSorryImperativeCorrection(
        tokens: List<LexicalToken>,
        markerIndex: Int,
    ): CorrectionInfo? {
        val beforeVerb = (0 until markerIndex).firstOrNull { index ->
            tokens[index].normalized in IMPERATIVE_CORRECTION_WORDS
        } ?: return null
        val afterVerb = (markerIndex + 1 until tokens.size).firstOrNull { index ->
            tokens[index].normalized in IMPERATIVE_CORRECTION_WORDS
        } ?: return null
        if (tokens[beforeVerb].normalized != tokens[afterVerb].normalized) return null

        fun correctionTarget(verb: Int, endExclusive: Int): Int? {
            val toIndex = (verb + 1 until endExclusive).lastOrNull { index ->
                tokens[index].normalized == "to"
            }
            if (toIndex != null) {
                return (toIndex + 1 until endExclusive).firstOrNull { index ->
                    tokens[index].normalized !in ALLOWED_GRAMMAR_ADDITIONS &&
                        tokens[index].normalized !in INTENT_LEADING_WORDS
                }
            }
            return (verb + 1 until endExclusive).lastOrNull { index ->
                tokens[index].normalized !in ALLOWED_GRAMMAR_ADDITIONS
            }
        }

        val supersededTarget = correctionTarget(beforeVerb, markerIndex) ?: beforeVerb
        val replacementTarget = correctionTarget(afterVerb, tokens.size) ?: afterVerb
        return CorrectionInfo(
            markerIndices = setOf(markerIndex),
            supersededTokenIndices = (beforeVerb until markerIndex).toSet(),
            supersededComparisonTokenIndex = supersededTarget,
            replacementTokenIndex = replacementTarget,
            replacementMustBeRetained = true,
        )
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
        if (intentIndex !in optionalRawIndices && intentWord !in candidateWords) {
            return "Model did not preserve the dictated intent"
        }

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
    private val REMOVABLE_DISCOURSE_WORDS = setOf(
        "well", "okay", "ok", "anyway", "basically",
    )
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
    private val NUMBER_WORD_VALUES = mapOf(
        "zero" to 0, "one" to 1, "two" to 2, "three" to 3, "four" to 4,
        "five" to 5, "six" to 6, "seven" to 7, "eight" to 8, "nine" to 9,
        "ten" to 10, "eleven" to 11, "twelve" to 12, "thirteen" to 13,
        "fourteen" to 14, "fifteen" to 15, "sixteen" to 16, "seventeen" to 17,
        "eighteen" to 18, "nineteen" to 19, "twenty" to 20, "thirty" to 30,
        "forty" to 40, "fifty" to 50, "sixty" to 60, "seventy" to 70,
        "eighty" to 80, "ninety" to 90, "hundred" to 100, "thousand" to 1_000,
        "million" to 1_000_000, "billion" to 1_000_000_000,
        "first" to 1, "second" to 2, "third" to 3, "fourth" to 4,
        "fifth" to 5, "sixth" to 6, "seventh" to 7, "eighth" to 8,
        "ninth" to 9, "tenth" to 10, "eleventh" to 11, "twelfth" to 12,
    )
    private val SINGLE_DIGIT_WORDS = setOf(
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    )
    private val TIME_CUE_WORDS = setOf(
        "at", "before", "after", "around", "by", "until", "from", "about",
    )
    private const val TIME_CUE_LOOKBACK_TOKENS = 6
    private val TIME_SUFFIX_WORDS = setOf("am", "pm", "a.m", "p.m")
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
        "deploy",
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
