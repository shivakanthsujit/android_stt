package dev.localflow.dictation.stt.benchmark

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.fail
import org.junit.Test

class CleanupBenchmarkActivityTest {
    @Test
    fun warmupsStayFirstAndUseTheFirstCase() {
        val jobs = buildCleanupBenchmarkJobOrder(
            caseCount = 3,
            warmupRuns = 2,
            measuredRepeats = 2,
        )

        assertEquals(
            listOf(
                CleanupBenchmarkJobOrderEntry(0, CLEANUP_BENCHMARK_PHASE_WARMUP, 0),
                CleanupBenchmarkJobOrderEntry(0, CLEANUP_BENCHMARK_PHASE_WARMUP, 1),
            ),
            jobs.take(2),
        )
    }

    @Test
    fun measuredJobsAreRepeatMajorAndRotateTheWarmupCaseToLast() {
        val jobs = buildCleanupBenchmarkJobOrder(
            caseCount = 3,
            warmupRuns = 1,
            measuredRepeats = 2,
        )
        val measured = jobs.filter { it.phase == CLEANUP_BENCHMARK_PHASE_MEASURED }

        assertEquals(listOf(1, 2, 0, 1, 2, 0), measured.map { it.caseIndex })
        assertEquals(listOf(0, 0, 0, 1, 1, 1), measured.map { it.repeatIndex })
        assertNotEquals(jobs.first().caseIndex, measured.first().caseIndex)
        assertNotEquals(measured[2].caseIndex, measured[3].caseIndex)
        jobs.zipWithNext().forEach { (previous, next) ->
            assertNotEquals(previous.caseIndex, next.caseIndex)
        }
    }

    @Test
    fun oneCaseRetainsDeterministicOrderingWhenSeparationIsImpossible() {
        val jobs = buildCleanupBenchmarkJobOrder(
            caseCount = 1,
            warmupRuns = 1,
            measuredRepeats = 2,
        )

        assertEquals(listOf(0, 0, 0), jobs.map { it.caseIndex })
        assertEquals(
            listOf(
                CLEANUP_BENCHMARK_PHASE_WARMUP,
                CLEANUP_BENCHMARK_PHASE_MEASURED,
                CLEANUP_BENCHMARK_PHASE_MEASURED,
            ),
            jobs.map { it.phase },
        )
        assertEquals(listOf(0, 0, 1), jobs.map { it.repeatIndex })
    }

    @Test
    fun invalidJobCountsAreRejected() {
        assertRejected { buildCleanupBenchmarkJobOrder(0, 1, 1) }
        assertRejected { buildCleanupBenchmarkJobOrder(1, -1, 1) }
        assertRejected { buildCleanupBenchmarkJobOrder(1, 1, 0) }
    }

    @Test
    fun cacheBenchmarksRequireEnoughUniqueCasesToEvictAFullPrompt() {
        requireCleanupBenchmarkCacheSeparation(caseCount = 5, cacheMaxEntries = 4)

        assertRejected {
            requireCleanupBenchmarkCacheSeparation(caseCount = 4, cacheMaxEntries = 4)
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
}
