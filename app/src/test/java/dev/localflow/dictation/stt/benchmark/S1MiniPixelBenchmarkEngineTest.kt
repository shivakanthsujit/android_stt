package dev.localflow.dictation.stt.benchmark

import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class S1MiniPixelBenchmarkEngineTest {
    @Test
    fun publisherPromptAndControlLineArePinned() {
        assertEquals(
            "6ecb6800f96b00cf612631552eff606a829feb2be8449fa95f9f150713b89327",
            sha256(S1MiniPixelBenchmarkEngine.SYSTEM_PROMPT),
        )
        assertEquals(
            "[Styling: semi-formal] [Structure: prose] [Context: general]",
            S1MiniPixelBenchmarkEngine.CONTROL_LINE,
        )
        assertEquals(
            "s1-mini-v1-publisher",
            S1MiniPixelBenchmarkEngine.PROMPT_PROFILE,
        )
        assertEquals(78, S1MiniPixelBenchmarkEngine.EXPECTED_FIXED_PROMPT_TOKENS)
    }

    @Test
    fun debugConfigAcceptsOnlyThePlannedMatrix() {
        listOf(4_096, 3_072, 2_560).forEach { contextTokens ->
            listOf<Int?>(null, 2, 3, 4).forEach { cpuThreads ->
                listOf<Int?>(null, 32, 64).forEach { cacheMemoryMb ->
                    S1MiniPixelBenchmarkEngine.Config(
                        contextTokens = contextTokens,
                        cpuThreads = cpuThreads,
                        cacheMemoryMb = cacheMemoryMb,
                    )
                }
            }
        }

        assertRejected { S1MiniPixelBenchmarkEngine.Config(contextTokens = 2_048) }
        assertRejected { S1MiniPixelBenchmarkEngine.Config(contextTokens = 4_097) }
        assertRejected { S1MiniPixelBenchmarkEngine.Config(cpuThreads = 1) }
        assertRejected { S1MiniPixelBenchmarkEngine.Config(cpuThreads = 5) }
        assertRejected { S1MiniPixelBenchmarkEngine.Config(cacheMemoryMb = 0) }
        assertRejected { S1MiniPixelBenchmarkEngine.Config(cacheMemoryMb = 128) }
    }

    @Test
    fun cacheOffPreservesImplicitThreadsAndMmap() {
        val config = S1MiniPixelBenchmarkEngine.Config()
        val absentCacheRoot = File(
            System.getProperty("java.io.tmpdir"),
            "s1-mini-cache-off-${System.nanoTime()}",
        )
        val options = config.toModelLoadingOptions(absentCacheRoot)

        assertEquals(S1MiniPixelBenchmarkEngine.CPU_THREADS_MODE_IMPLICIT, config.cpuThreadsMode)
        assertNull(config.cpuThreads)
        assertFalse(config.cacheEnabled)
        assertEquals(0L, config.cacheMaxMemoryBytes)
        assertEquals(0, config.cacheMaxEntries)
        assertEquals(0, config.cacheMaxDiskEntries)
        assertTrue(config.cacheDiskDisabled)
        assertNull(options.cacheOptions)
        assertFalse(absentCacheRoot.exists())
        assertTrue(options.cpuThreads > 0)
        assertEquals(S1MiniPixelBenchmarkEngine.MODEL_CONTEXT_TOKENS, options.contextSize)
        assertEquals(true, options.useMmap)
    }

    @Test
    fun memoryCacheUsesFourEntriesAndDisablesDisk() {
        val config = S1MiniPixelBenchmarkEngine.Config(
            contextTokens = 2_560,
            cpuThreads = 3,
            cacheMemoryMb = 32,
        )
        val cacheRoot = Files.createTempDirectory("s1-mini-cache-test").toFile()
        val expectedCachePath =
            File(cacheRoot, S1MiniPixelBenchmarkEngine.CACHE_DIRECTORY).canonicalPath
        val options = try {
            config.toModelLoadingOptions(cacheRoot).also { loadingOptions ->
                val cache = requireNotNull(loadingOptions.cacheOptions)
                assertTrue(File(cache.path).isDirectory)
            }
        } finally {
            cacheRoot.deleteRecursively()
        }
        val cache = requireNotNull(options.cacheOptions)

        assertEquals(S1MiniPixelBenchmarkEngine.CPU_THREADS_MODE_EXPLICIT, config.cpuThreadsMode)
        assertEquals(3, options.cpuThreads)
        assertEquals(2_560, options.contextSize)
        assertEquals(expectedCachePath, cache.path)
        assertTrue(cache.enabled)
        assertEquals(0, cache.maxEntries)
        assertEquals(0, cache.maxEntriesDisk)
        assertEquals(4, cache.maxEntriesMemory)
        assertEquals(32L * S1MiniPixelBenchmarkEngine.BYTES_PER_MIB, cache.maxBytesMemory)
        assertTrue(cache.diskDisabled)
    }

    @Test
    fun requestMustFitSelectedContext() {
        S1MiniPixelBenchmarkEngine.requireContextCapacity(
            promptTokens = 1_228,
            maxOutputTokens = 1_332,
            contextTokens = 2_560,
        )

        assertRejected {
            S1MiniPixelBenchmarkEngine.requireContextCapacity(
                promptTokens = 1_229,
                maxOutputTokens = 1_332,
                contextTokens = 2_560,
            )
        }
    }

    private fun assertRejected(block: () -> Unit) {
        try {
            block()
            fail("Expected IllegalArgumentException")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    private fun sha256(value: String): String =
        MessageDigest.getInstance("SHA-256")
            .digest(value.toByteArray(Charsets.UTF_8))
            .joinToString("") { byte -> "%02x".format(byte) }
}
