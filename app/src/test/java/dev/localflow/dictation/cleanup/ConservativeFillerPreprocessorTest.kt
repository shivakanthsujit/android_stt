package dev.localflow.dictation.cleanup

import org.junit.Assert.assertEquals
import org.junit.Test

class ConservativeFillerPreprocessorTest {
    @Test
    fun removesStandaloneLowAmbiguityFillers() {
        val result = ConservativeFillerPreprocessor.prepare(
            "Um, uh, please, erm, send it. I was, um, thinking tomorrow.",
        )

        assertEquals("please send it. I was thinking tomorrow.", result.modelInputText)
        assertEquals(listOf("Um", "uh", "erm", "um"), result.removedFillers)
    }

    @Test
    fun removesUnpunctuatedStandaloneFillers() {
        val result = ConservativeFillerPreprocessor.prepare("I uh think we should um leave")

        assertEquals("I think we should leave", result.modelInputText)
        assertEquals(listOf("uh", "um"), result.removedFillers)
    }

    @Test
    fun preservesAmbiguousDiscourseWords() {
        val input = "Hmm, well, I like, you know, the current plan."

        assertEquals(input, ConservativeFillerPreprocessor.prepare(input).modelInputText)
    }

    @Test
    fun preservesQuotedAndCodeLikeOccurrences() {
        val input = "Say \"um\", 'erm', and `uh`; keep /tmp/um/file and uh-oh."

        val result = ConservativeFillerPreprocessor.prepare(input)

        assertEquals(input, result.modelInputText)
        assertEquals(emptyList<String>(), result.removedFillers)
    }

    @Test
    fun preservesUppercaseAcronyms() {
        val input = "UM and UH use ERM in this identifier."

        assertEquals(input, ConservativeFillerPreprocessor.prepare(input).modelInputText)
    }

    @Test
    fun preservesTitlecaseNameLikeTokenWithoutFillerPunctuation() {
        val input = "Um Kulthum is the protected name."

        assertEquals(input, ConservativeFillerPreprocessor.prepare(input).modelInputText)
    }

    @Test
    fun preservesParagraphBreaks() {
        val result = ConservativeFillerPreprocessor.prepare("Um, first paragraph.\n\nUh, second one.")

        assertEquals("first paragraph.\n\nsecond one.", result.modelInputText)
    }

    @Test
    fun fillerOnlyInputBecomesEmpty() {
        val result = ConservativeFillerPreprocessor.prepare("um, uh, erm")

        assertEquals("", result.modelInputText)
        assertEquals(listOf("um", "uh", "erm"), result.removedFillers)
    }
}
