package dev.localflow.dictation.cleanup

/** Result of the deterministic, pre-model filler pass. */
data class FillerPreprocessingResult(
    val modelInputText: String,
    val removedFillers: List<String>,
)

/**
 * Removes only low-ambiguity standalone hesitation tokens before model inference.
 *
 * Ambiguous discourse words (for example, "like", "well", and "you know") are deliberately not
 * included. Uppercase acronyms, quoted text, hyphenated words, paths, and identifier-like tokens
 * are also preserved. The original transcript remains separate from [modelInputText].
 */
object ConservativeFillerPreprocessor {
    private val removableFillers = setOf("um", "uh", "erm")
    private val protectedAdjacentCharacters = setOf('/', '\\', '.', '@', '#', '_', '-', ':')
    private val repeatedHorizontalSpace = Regex("[ \\t]{2,}")
    private val spaceBeforePunctuation = Regex("[ \\t]+([,.;:!?])")

    fun prepare(text: String): FillerPreprocessingResult {
        if (text.isBlank()) {
            return FillerPreprocessingResult(text.trim(), emptyList())
        }

        val marker = unusedMarker(text)
        val marked = StringBuilder(text.length)
        val removed = mutableListOf<String>()
        var quote: Char? = null
        var index = 0

        while (index < text.length) {
            val character = text[index]
            quote = updatedQuoteState(text, index, quote)
            if (!character.isLetter()) {
                marked.append(character)
                index += 1
                continue
            }

            val start = index
            while (index < text.length && text[index].isLetter()) index += 1
            val token = text.substring(start, index)
            val previous = text.getOrNull(start - 1)
            val next = text.getOrNull(index)
            val isAllUppercase = token.any(Char::isLetter) && token.all {
                !it.isLetter() || it.isUpperCase()
            }
            val isTitlecase = token.first().isUpperCase() && token.drop(1).all(Char::isLowerCase)
            val titlecaseLooksLikeHesitation = isTitlecase && next == ','
            val isProtectedLiteral = quote != null ||
                previous in protectedAdjacentCharacters ||
                next in protectedAdjacentCharacters
            if (
                token.lowercase() in removableFillers &&
                !isAllUppercase &&
                (!isTitlecase || titlecaseLooksLikeHesitation) &&
                !isProtectedLiteral
            ) {
                marked.append(marker)
                removed += token
            } else {
                marked.append(token)
            }
        }

        val markerPattern = Regex.escape(marker.toString())
        val cleaned = marked.toString().split('\n').joinToString("\n") { line ->
            cleanLine(line, markerPattern)
        }.trim()
        return FillerPreprocessingResult(cleaned, removed)
    }

    private fun cleanLine(line: String, markerPattern: String): String {
        var cleaned = line
        val atStart = Regex("^[ \\t]*$markerPattern[ \\t]*,?[ \\t]*")
        val betweenCommas = Regex(",[ \\t]*$markerPattern[ \\t]*,[ \\t]*")
        val beforeComma = Regex("$markerPattern[ \\t]*,[ \\t]*")
        val afterComma = Regex(",[ \\t]*$markerPattern(?=[ \\t]|$)")
        while (cleaned.contains(Regex(markerPattern))) {
            val previous = cleaned
            cleaned = cleaned
                .replace(atStart, "")
                .replace(betweenCommas, " ")
                .replace(beforeComma, "")
                .replace(afterComma, "")
            if (cleaned == previous) break
        }
        cleaned = cleaned
            .replace(Regex(markerPattern), "")
            .replace(repeatedHorizontalSpace, " ")
            .replace(spaceBeforePunctuation, "$1")
        return cleaned.trim()
    }

    private fun updatedQuoteState(text: String, index: Int, current: Char?): Char? {
        val character = text[index]
        return when (character) {
            '"' -> if (current == '"') null else if (current == null) '"' else current
            '“' -> if (current == null) '”' else current
            '”' -> if (current == '”') null else current
            '`' -> if (current == '`') null else if (current == null) '`' else current
            '\'', '‘', '’' -> {
                val insideWord = text.getOrNull(index - 1)?.isLetterOrDigit() == true &&
                    text.getOrNull(index + 1)?.isLetterOrDigit() == true
                if (insideWord) {
                    current
                } else if (current == '\'') {
                    null
                } else if (current == null) {
                    '\''
                } else {
                    current
                }
            }
            else -> current
        }
    }

    private fun unusedMarker(text: String): Char =
        PRIVATE_MARKERS.firstOrNull { marker -> marker !in text }
            ?: error("Input contains every reserved preprocessing marker")

    private val PRIVATE_MARKERS = charArrayOf('\uE000', '\uE001', '\uE002')
}
