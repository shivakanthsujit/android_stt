package dev.localflow.dictation.cleanup

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class S1MiniTranscriptChunkerTest {
    @Test
    fun leavesShortTranscriptInOnePass() {
        val chunks = split("one two three", maxTokens = 4)

        assertEquals(listOf("one two three"), chunks.map { it.text })
        assertEquals("", chunks.single().separatorAfter)
    }

    @Test
    fun prefersSttEndOfUtteranceBoundaries() {
        val text = "one two three four five six"
        val chunks = runBlocking {
            S1MiniTranscriptChunker.split(
                text = text,
                preferredBoundaryOffsets = listOf("one two three".length),
                maxTokens = 3,
                tokenCount = ::wordCount,
            )
        }

        assertEquals(listOf("one two three", "four five six"), chunks.map { it.text })
    }

    @Test
    fun usesWrittenSentenceBoundariesBeforeWordFallback() {
        val text = "One two. Three four. Five six."
        val chunks = split(text, maxTokens = 4)

        assertEquals(listOf("One two. Three four.", "Five six."), chunks.map { it.text })
    }

    @Test
    fun boundsLongUnpunctuatedSpeechAtWhitespace() {
        val chunks = split("one two three four five six seven", maxTokens = 3)

        assertEquals(listOf("one two three", "four five six", "seven"), chunks.map { it.text })
        assertTrue(chunks.all { wordCount(it.text) <= 3 })
    }

    @Test
    fun preservesParagraphSeparatorAcrossPasses() {
        val chunks = split("one two\n\nthree four", maxTokens = 2)

        assertEquals(listOf("one two", "three four"), chunks.map { it.text })
        assertEquals("\n\n", chunks.first().separatorAfter)
    }

    @Test
    fun reconstructsOriginalWhitespaceBetweenPasses() {
        val text = "one two.   three four.\n\nfive six."
        val chunks = split(text, maxTokens = 2)

        assertEquals(
            text,
            buildString {
                chunks.forEach { chunk ->
                    append(chunk.text)
                    append(chunk.separatorAfter)
                }
            },
        )
    }

    @Test
    fun preservesWhitespaceIncludedInSttBoundaryOffset() {
        val text = "one two   three four"
        val chunks = runBlocking {
            S1MiniTranscriptChunker.split(
                text = text,
                preferredBoundaryOffsets = listOf("one two   ".length),
                maxTokens = 2,
                tokenCount = ::wordCount,
            )
        }

        assertEquals("   ", chunks.first().separatorAfter)
        assertEquals(text, chunks.joinToString("") { it.text + it.separatorAfter })
    }

    private fun split(text: String, maxTokens: Int): List<S1MiniTranscriptChunk> = runBlocking {
        S1MiniTranscriptChunker.split(
            text = text,
            preferredBoundaryOffsets = emptyList(),
            maxTokens = maxTokens,
            tokenCount = ::wordCount,
        )
    }

    private fun wordCount(text: String): Int = text.trim().split(Regex("\\s+")).size
}
