package dev.localflow.dictation.cleanup

/** A token-bounded transcript slice and the separator to restore after cleanup. */
internal data class S1MiniTranscriptChunk(
    val text: String,
    val separatorAfter: String,
)

/**
 * Greedily packs a completed transcript into model-card-sized cleanup passes.
 *
 * STT-provided EOU offsets and written sentence endings are preferred. A whitespace boundary is
 * used only when an unpunctuated sentence itself is too large for one pass.
 */
internal object S1MiniTranscriptChunker {
    suspend fun split(
        text: String,
        preferredBoundaryOffsets: List<Int>,
        maxTokens: Int,
        tokenCount: suspend (String) -> Int,
    ): List<S1MiniTranscriptChunk> {
        require(maxTokens > 0) { "Maximum chunk token count must be positive" }
        val normalized = text.trim()
        if (normalized.isEmpty()) return emptyList()
        if (tokenCount(normalized) <= maxTokens) {
            return listOf(S1MiniTranscriptChunk(normalized, ""))
        }

        val sentenceEnds = buildSet {
            preferredBoundaryOffsets
                .filter { it in 1 until normalized.length }
                .forEach(::add)
            sentenceBoundary.findAll(normalized).forEach { match -> add(match.range.last + 1) }
            paragraphBoundary.findAll(normalized).forEach { match -> add(match.range.first) }
        }.sorted()
        val wordEnds = whitespace.findAll(normalized)
            .map { match -> match.range.first }
            .filter { it > 0 }
            .toList()

        val chunks = mutableListOf<S1MiniTranscriptChunk>()
        var start = 0
        while (start < normalized.length) {
            start = skipWhitespace(normalized, start)
            if (start >= normalized.length) break

            val end = farthestFittingBoundary(
                text = normalized,
                start = start,
                boundaries = sentenceEnds,
                maxTokens = maxTokens,
                tokenCount = tokenCount,
            ) ?: farthestFittingBoundary(
                text = normalized,
                start = start,
                boundaries = wordEnds,
                maxTokens = maxTokens,
                tokenCount = tokenCount,
            ) ?: normalized.length.also {
                require(tokenCount(normalized.substring(start).trim()) <= maxTokens) {
                    "A single transcript token exceeds S1-mini's recommended chunk size"
                }
            }

            var contentEnd = end
            while (contentEnd > start && normalized[contentEnd - 1].isWhitespace()) {
                contentEnd -= 1
            }
            val rawChunk = normalized.substring(start, contentEnd)
            val chunkText = rawChunk.trim()
            require(chunkText.isNotEmpty()) { "S1-mini chunking produced an empty pass" }
            require(tokenCount(chunkText) <= maxTokens) {
                "S1-mini chunking exceeded the recommended token ceiling"
            }

            val nextStart = skipWhitespace(normalized, end)
            chunks += S1MiniTranscriptChunk(
                text = chunkText,
                separatorAfter = if (nextStart < normalized.length) {
                    normalized.substring(contentEnd, nextStart)
                } else {
                    ""
                },
            )
            start = nextStart
        }
        return chunks
    }

    private suspend fun farthestFittingBoundary(
        text: String,
        start: Int,
        boundaries: List<Int>,
        maxTokens: Int,
        tokenCount: suspend (String) -> Int,
    ): Int? {
        var best: Int? = null
        for (boundary in boundaries) {
            if (boundary <= start) continue
            val candidate = text.substring(start, boundary).trim()
            if (candidate.isEmpty()) continue
            if (tokenCount(candidate) > maxTokens) break
            best = boundary
        }
        if (best != null) return best

        val remaining = text.substring(start).trim()
        return if (tokenCount(remaining) <= maxTokens) text.length else null
    }

    private fun skipWhitespace(text: String, offset: Int): Int {
        var result = offset
        while (result < text.length && text[result].isWhitespace()) result += 1
        return result
    }

    private val sentenceBoundary = Regex("[.!?]+[\\\"'”’)]*(?=\\s|$)")
    private val paragraphBoundary = Regex("\\n\\s*\\n")
    private val whitespace = Regex("\\s+")
}
