package dev.localflow.dictation.cleanup

/** Minimal runtime validity checks for local cleanup generation. */
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

    @Suppress("UNUSED_PARAMETER")
    fun fallbackReason(
        rawText: String,
        candidate: String,
        hitOutputTokenLimit: Boolean,
    ): String? = when {
        candidate.isBlank() -> "Model returned empty text"
        hitOutputTokenLimit -> "Model reached the output token limit"
        else -> null
    }

    private val KNOWN_OUTPUT_PREFIXES = listOf(
        "Cleaned transcript:",
        "Cleaned text:",
        "Output:",
    )
    private val KNOWN_OUTPUT_SUFFIXES = listOf(
        "<|im_end|>",
        "<|endoftext|>",
        "<|eot_id|>",
    )
}
