package dev.localflow.llamacppbenchmark

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class S1PromptGoldenTest {
    @Test
    fun hostLlamaCppGoldenMatchesExactPromptContract() {
        val resource = requireNotNull(javaClass.classLoader?.getResource("s1_prompt_golden_v1.json"))
        val root = JSONObject(resource.readText())
        assertEquals(1, root.getInt("schema_version"))
        assertEquals(S1Contract.MODEL_SHA256, root.getString("model_sha256"))
        assertEquals(S1Contract.PROMPT_PROFILE, root.getString("prompt_profile"))

        val cases = root.getJSONArray("cases")
        assertEquals(3, cases.length())
        repeat(cases.length()) { index ->
            val case = cases.getJSONObject(index)
            assertEquals(
                setOf("id", "raw", "raw_token_ids", "rendered_prompt", "prompt_token_ids"),
                case.keys().asSequence().toSet(),
            )
            val raw = case.getString("raw")
            val rawIds = case.getJSONArray("raw_token_ids")
            val promptIds = case.getJSONArray("prompt_token_ids")
            assertTrue(raw.isNotBlank())
            assertEquals(S1Contract.renderPrompt(raw), case.getString("rendered_prompt"))
            assertEquals(
                S1Contract.EXPECTED_FIXED_PROMPT_TOKENS,
                promptIds.length() - rawIds.length(),
            )
            assertEquals(
                (13 * rawIds.length() + 9) / 10 + 32,
                S1Contract.outputCap(rawIds.length()),
            )
            assertFalse(case.has("expected"))
            assertFalse(case.has("output"))
        }
    }
}
