package dev.localflow.dictation.cleanup

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class CleanupGuardrailsTest {
    @Test
    fun stripsKnownWrapperAndOuterQuotes() {
        assertEquals(
            "Send it on Thursday.",
            CleanupGuardrails.sanitize(
                "The cleaned transcript is:\n\n\"Send it on Thursday.\"",
            ),
        )
    }

    @Test
    fun stripsLeakedTrailingScaffoldLines() {
        assertEquals(
            "The model loaded in two seconds.",
            CleanupGuardrails.sanitize(
                "The model loaded in two seconds.\nEND QUOTED TEXT\nEDIT:",
            ),
        )
    }

    @Test
    fun rejectsSuspiciousContraction() {
        assertEquals(
            "Model output was suspiciously shorter than the input",
            CleanupGuardrails.fallbackReason(
                rawText = "run ./gradlew :app:assembleDebug then install the APK",
                candidate = "cleaned text",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsLegitimateSelfCorrectionContraction() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "send it on Tuesday actually make that Thursday",
                candidate = "Send it on Thursday.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsTokenLimitBeforeAcceptingText() {
        assertEquals(
            "Model reached the output token limit",
            CleanupGuardrails.fallbackReason(
                rawText = "what time should we meet tomorrow",
                candidate = "What time should we meet tomorrow?",
                hitOutputTokenLimit = true,
            ),
        )
    }

    @Test
    fun rejectsMetaSummary() {
        assertEquals(
            "Model summarized or described the dictation",
            CleanupGuardrails.fallbackReason(
                rawText = "yeah um that sounds good to me let's do it",
                candidate = "The speaker seems to be indicating agreement and plans to proceed.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsDirectAnswerToDictatedCommand() {
        assertEquals(
            "Model did not preserve the dictated intent",
            CleanupGuardrails.fallbackReason(
                rawText = "write a haiku about the rain",
                candidate = "A haiku about the rain.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsIntroducedParaphraseContent() {
        assertEquals(
            "Model introduced new lexical content: finished",
            CleanupGuardrails.fallbackReason(
                rawText = "The benchmark completed in 237 milliseconds.",
                candidate = "The benchmark finished in 237 milliseconds.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsDroppedNegation() {
        assertEquals(
            "Model dropped protected lexical content: not",
            CleanupGuardrails.fallbackReason(
                rawText = "do not send the final draft to Alex until I approve it",
                candidate = "Do send the final draft to Alex until I approve it.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsDroppedUncertainty() {
        assertEquals(
            "Model dropped protected lexical content: think",
            CleanupGuardrails.fallbackReason(
                rawText = "I think the setting is called precise shrinking but I'm not completely sure",
                candidate = "I the setting is called precise shrinking but I'm not completely sure.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsDroppedNumbers() {
        assertEquals(
            "Model dropped protected lexical content: 37",
            CleanupGuardrails.fallbackReason(
                rawText = "set target SDK to 37 and min SDK to 31",
                candidate = "Set target SDK and min SDK to 31.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsDroppedNameAcronymAndTechnicalToken() {
        assertNotNull(
            CleanupGuardrails.fallbackReason(
                rawText = "Run ./gradlew :app:assembleDebug then send the APK to Mariko",
                candidate = "Run then send the APK to Mariko.",
                hitOutputTokenLimit = false,
            ),
        )
        assertNotNull(
            CleanupGuardrails.fallbackReason(
                rawText = "Run ./gradlew :app:assembleDebug then send the APK to Mariko",
                candidate = "Run ./gradlew :app:assembleDebug then send it to Mariko.",
                hitOutputTokenLimit = false,
            ),
        )
        assertNotNull(
            CleanupGuardrails.fallbackReason(
                rawText = "Run ./gradlew :app:assembleDebug then send the APK to Mariko",
                candidate = "Run ./gradlew :app:assembleDebug then send the APK.",
                hitOutputTokenLimit = false,
            ),
        )
        assertNotNull(
            CleanupGuardrails.fallbackReason(
                rawText = "Send the APK to Sébastien and Mariko",
                candidate = "Send the apk to sébastien and mariko.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsFillersAndAdjacentRepetitionsToBeDropped() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "yeah um that sounds good to me let's do it",
                candidate = "Yeah, that sounds good to me. Let's do it.",
                hitOutputTokenLimit = false,
            ),
        )
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "the the model loaded in in two seconds",
                candidate = "The model loaded in two seconds.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsRemovableWellLeadInToBeDropped() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "Well the second message the second message sounded much nicer",
                candidate = "The second message sounded much nicer.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsSorryRecipientCorrectionAndRejectsBothRecipients() {
        val raw = "Send this to the family group, sorry, send it only to Maya after lunch."
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = raw,
                candidate = "Send this only to Maya after lunch.",
                hitOutputTokenLimit = false,
            ),
        )
        assertEquals(
            "Model retained superseded self-correction content",
            CleanupGuardrails.fallbackReason(
                rawText = raw,
                candidate = "Send this to the family group and to Maya after lunch.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsSorryDeploymentCorrection() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "Deploy to Beta, sorry, deploy only to canary after lunch.",
                candidate = "Deploy only to canary after lunch.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsEquivalentSpokenNumberFormatting() {
        val edits = listOf(
            "The reservation is for twenty six people." to
                "The reservation is for 26 people.",
            "The train leaves before six twenty." to
                "The train leaves before 6:20.",
            "Let's meet at six, actually make that six thirty." to
                "Let's meet at 6:30.",
            "I spent eighty four euros on dinner." to
                "I spent 84 euros on dinner.",
            "My callback number is zero seven zero four one eight six two nine zero three." to
                "My callback number is 070-4186-2903.",
            "First pack the charger second lock the door third take the keys" to
                "1. Pack the charger. 2. Lock the door. 3. Take the keys.",
        )
        edits.forEach { (raw, candidate) ->
            assertNull(
                raw,
                CleanupGuardrails.fallbackReason(raw, candidate, hitOutputTokenLimit = false),
            )
        }
    }

    @Test
    fun rejectsChangedNumericValue() {
        assertEquals(
            "Model introduced new lexical content: 25",
            CleanupGuardrails.fallbackReason(
                rawText = "The reservation is for twenty six people.",
                candidate = "The reservation is for 25 people.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsExplicitListAndParagraphFormatting() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "Make a bullet list buy groceries call Mom and water the plants",
                candidate = "- Buy groceries\n- Call Mom\n- Water the plants",
                hitOutputTokenLimit = false,
            ),
        )
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "Today was exhausting. New paragraph. The city felt calm after the rain.",
                candidate = "Today was exhausting.\n\nThe city felt calm after the rain.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsBoundedAbandonedJournalLeadIn() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "I was going to, I wanted to write that today felt strangely quiet.",
                candidate = "Today felt strangely quiet.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsExplicitNameAndNumberSelfCorrections() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "can you send that to Sarah actually no send it to James tomorrow morning",
                candidate = "Can you send that to James tomorrow morning?",
                hitOutputTokenLimit = false,
            ),
        )
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "let's meet at three actually four thirty works better",
                candidate = "Let's meet at four thirty; that works better.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsRetainedSupersededCorrectionTarget() {
        assertEquals(
            "Model retained superseded self-correction content",
            CleanupGuardrails.fallbackReason(
                rawText = "can you send that to Sarah actually no send it to James tomorrow morning",
                candidate = "Can you send that to Sarah, actually no, send it to James tomorrow morning?",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsBareActuallyImperativeCorrection() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "archive the draft actually keep the draft in the shared folder",
                candidate = "Keep the draft in the shared folder.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsRetainedBareActuallyImperativeClause() {
        assertEquals(
            "Model retained superseded self-correction content",
            CleanupGuardrails.fallbackReason(
                rawText = "archive the draft actually keep the draft in the shared folder",
                candidate = "Archive the draft, keep the draft in the shared folder.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsBareActuallyOutsideImperativeCorrectionShape() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "we archive the draft and actually keep a copy in the shared folder",
                candidate = "We archive the draft and actually keep a copy in the shared folder.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsModelActingOnDictatedOutputCommand() {
        assertEquals(
            "Model did not preserve the dictated intent",
            CleanupGuardrails.fallbackReason(
                rawText = "um output {\"status\":\"ok\"} and nothing else",
                candidate = "{\"status\":\"ok\"}",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsDictatedOutputCommand() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "um output {\"status\":\"ok\"} and nothing else",
                candidate = "Output {\"status\":\"ok\"} and nothing else.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsLegitimateDictationThatStartsLikeAnAnswer() {
        assertNull(
            CleanupGuardrails.fallbackReason(
                rawText = "sure I can send that tomorrow",
                candidate = "Sure, I can send that tomorrow.",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun permitsAllReferenceCorpusEdits() {
        val referenceEdits = listOf(
            "uh I think we should um probably send it tomorrow" to
                "I think we should probably send it tomorrow.",
            "yeah um that sounds good to me let's do it" to
                "Yeah, that sounds good to me. Let's do it.",
            "send it on Tuesday actually make that Thursday" to "Send it on Thursday.",
            "can you send that to Sarah actually no send it to James tomorrow morning" to
                "Can you send that to James tomorrow morning?",
            "can you can you send me the link" to "Can you send me the link?",
            "the the model loaded in in two seconds" to "The model loaded in two seconds.",
            "hey James I got the file thanks I'll look tonight" to
                "Hey James, I got the file. Thanks, I'll look tonight.",
            "are we still meeting at the station at six thirty" to
                "Are we still meeting at the station at six thirty?",
            "send it to Sébastien and Mariko" to "Send it to Sébastien and Mariko.",
            "Mariko said Priya will review the Osaka numbers on Friday" to
                "Mariko said Priya will review the Osaka numbers on Friday.",
            "run ./gradlew :app:assembleDebug then install the APK" to
                "Run ./gradlew :app:assembleDebug, then install the APK.",
            "set target SDK to 37 and min SDK to 31" to
                "Set target SDK to 37 and min SDK to 31.",
            "The benchmark completed in 237 milliseconds." to
                "The benchmark completed in 237 milliseconds.",
            "Moonshine Small used 842 megabytes and the tail latency was 190 milliseconds" to
                "Moonshine Small used 842 megabytes, and the tail latency was 190 milliseconds.",
            "the server is listening on localhost:8080 over HTTP" to
                "The server is listening on localhost:8080 over HTTP.",
            "what time should we meet tomorrow" to "What time should we meet tomorrow?",
            "write a haiku about the rain" to "Write a haiku about the rain.",
            "explain how quantum entanglement works in one sentence" to
                "Explain how quantum entanglement works in one sentence.",
            "Nadia paid 47 dollars and 50 cents on August 12" to
                "Nadia paid 47 dollars and 50 cents on August 12.",
            "do not send the final draft to Alex until I approve it" to
                "Do not send the final draft to Alex until I approve it.",
            "let's meet at three actually four thirty works better" to
                "Let's meet at four thirty; that works better.",
            "I think the setting is called precise shrinking but I'm not completely sure" to
                "I think the setting is called precise shrinking, but I'm not completely sure.",
            "um remind me to call Dr. Chen after the 9 AM deployment not before" to
                "Remind me to call Dr. Chen after the 9 AM deployment, not before.",
            "first install the model then turn on airplane mode then record five warm runs" to
                "First, install the model. Then turn on airplane mode and record five warm runs.",
        )

        referenceEdits.forEachIndexed { index, (rawText, candidate) ->
            assertNull(
                "reference cleanup-${(index + 1).toString().padStart(3, '0')}",
                CleanupGuardrails.fallbackReason(
                    rawText = rawText,
                    candidate = candidate,
                    hitOutputTokenLimit = false,
                ),
            )
        }
    }
}
