package dev.localflow.llamacppbenchmark

import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class BenchmarkContractsTest {
    @Test
    fun publisherConstantsAndOutputCapArePinned() {
        assertEquals(
            "6ecb6800f96b00cf612631552eff606a829feb2be8449fa95f9f150713b89327",
            sha256(S1Contract.SYSTEM_PROMPT),
        )
        assertEquals(
            "[Styling: semi-formal] [Structure: prose] [Context: general]",
            S1Contract.CONTROL_LINE,
        )
        assertEquals(34, S1Contract.outputCap(1))
        assertEquals(45, S1Contract.outputCap(10))
        assertEquals(1_332, S1Contract.outputCap(1_000))
        assertThrows(IllegalArgumentException::class.java) { S1Contract.outputCap(0) }
        assertThrows(IllegalArgumentException::class.java) { S1Contract.outputCap(1_001) }
    }

    @Test
    fun measuredJobsAreRepeatMajorAndRotateWarmupCaseToLast() {
        val jobs = buildBenchmarkJobOrder(caseCount = 3, warmupRuns = 1, measuredRepeats = 2)

        assertEquals(BenchmarkJobOrderEntry(0, PHASE_WARMUP, 0), jobs.first())
        assertEquals(listOf(1, 2, 0, 1, 2, 0), jobs.drop(1).map { it.caseIndex })
        assertEquals(listOf(0, 0, 0, 1, 1, 1), jobs.drop(1).map { it.repeatIndex })
        jobs.zipWithNext().forEach { (previous, next) ->
            assertTrue(previous.caseIndex != next.caseIndex)
        }
    }

    @Test
    fun runtimeConfigAcceptsOnlyBoundedCpuMatrix() {
        BenchmarkConfig()
        BenchmarkConfig(
            contextTokens = 4_096,
            generationThreads = 8,
            batchThreads = 8,
            batchSize = 512,
            microBatchSize = 128,
            useMmap = false,
            flashAttention = true,
        )

        assertRejected { BenchmarkConfig(contextTokens = 2_048) }
        assertRejected { BenchmarkConfig(generationThreads = 1) }
        assertRejected { BenchmarkConfig(batchThreads = 3) }
        assertRejected { BenchmarkConfig(batchSize = 64) }
        assertRejected { BenchmarkConfig(batchSize = 128, microBatchSize = 256) }
        assertRejected { BenchmarkConfig(gpuLayers = 1) }
    }

    @Test
    fun transcriptParserRejectsExpectedOutputsAndPreservesEscaping() {
        val raw = "He said, \"line one\\nline two\" — 東京."
        val parsed = TranscriptCaseParser.parseLine(
            JSONObject()
                .put("id", "smoke-unicode")
                .put("raw", raw)
                .put("categories", JSONArray(listOf("smoke", "unicode")))
                .toString(),
            1,
        )
        assertEquals(raw, parsed.rawText)

        assertRejected {
            TranscriptCaseParser.parseLine(
                JSONObject()
                    .put("id", "forbidden")
                    .put("raw", "Transcript only.")
                    .put("categories", JSONArray())
                    .put("expected", "Not allowed.")
                    .toString(),
                2,
            )
        }
    }

    @Test
    fun recordRoundTripPreservesRawAndNativeOutputEscaping() {
        val raw = "Quote: \"hello\"\nSecond line — café"
        val output = "Clean \"text\"\nwith Unicode: 東京"
        val record = buildBenchmarkRecord(
            runId = "run-1",
            job = BenchmarkJobOrderEntry(0, PHASE_MEASURED, 0),
            case = TranscriptCase("smoke-1", raw, listOf("smoke")),
            maxOutputTokens = 40,
            modelSha256 = S1Contract.MODEL_SHA256,
            requestedConfig = BenchmarkConfig().toJson(),
            nativeModelInfo = JSONObject().put("schema_version", 1),
            appBuildInfo = JSONObject().put("build_type", "debug"),
            nativeGeneration = JSONObject()
                .put("raw_output", output)
                .put("completion_tokens", 4),
            hostMetrics = HostMetrics(12, 34, 56, 0),
            modelLoadMs = 78,
            createdAtUtc = "2026-08-22T00:00:00Z",
        )

        val reparsed = JSONObject(record.toString())
        assertEquals(raw, reparsed.getString("raw_text"))
        assertEquals(output, reparsed.getString("raw_output"))
        assertFalse(reparsed.has("expected"))
        assertFalse(reparsed.has("must_preserve"))
    }

    @Test
    fun nativeFieldsCannotOverwriteHostEvidence() {
        assertRejected {
            buildBenchmarkRecord(
                runId = "run-1",
                job = BenchmarkJobOrderEntry(0, PHASE_MEASURED, 0),
                case = TranscriptCase("smoke-1", "hello", listOf("smoke")),
                maxOutputTokens = 40,
                modelSha256 = S1Contract.MODEL_SHA256,
                requestedConfig = BenchmarkConfig().toJson(),
                nativeModelInfo = JSONObject(),
                appBuildInfo = JSONObject(),
                nativeGeneration = JSONObject().put("raw_text", "collision"),
                hostMetrics = HostMetrics(0, 0, 0, 0),
                modelLoadMs = 0,
                createdAtUtc = "2026-08-22T00:00:00Z",
            )
        }
    }

    private fun assertRejected(block: () -> Unit) {
        assertThrows(IllegalArgumentException::class.java) { block() }
    }

    private fun sha256(value: String): String =
        MessageDigest.getInstance("SHA-256")
            .digest(value.toByteArray(Charsets.UTF_8))
            .joinToString("") { byte -> "%02x".format(byte) }
}
