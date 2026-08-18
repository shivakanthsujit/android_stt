package dev.localflow.dictation.stt.benchmark

import java.io.File
import java.io.RandomAccessFile
import java.nio.charset.StandardCharsets

internal data class PcmAudio(
    val samples: FloatArray,
    val sampleRate: Int,
) {
    val durationMs: Double
        get() = samples.size * 1_000.0 / sampleRate
}

/** Strict reader for the canonical benchmark format: mono, signed PCM16 WAV. */
internal object Pcm16WavReader {
    fun read(file: File): PcmAudio {
        RandomAccessFile(file, "r").use { wav ->
            require(readFourCc(wav) == "RIFF") { "Not a RIFF file: ${file.name}" }
            readUInt32Le(wav) // RIFF container size.
            require(readFourCc(wav) == "WAVE") { "Not a WAVE file: ${file.name}" }

            var audioFormat: Int? = null
            var channelCount: Int? = null
            var sampleRate: Int? = null
            var bitsPerSample: Int? = null
            var dataOffset: Long? = null
            var dataLength: Long? = null

            while (wav.filePointer + CHUNK_HEADER_BYTES <= wav.length()) {
                val chunkId = readFourCc(wav)
                val chunkLength = readUInt32Le(wav)
                val chunkStart = wav.filePointer
                val chunkEnd = chunkStart + chunkLength
                require(chunkEnd >= chunkStart && chunkEnd <= wav.length()) {
                    "Invalid $chunkId chunk in ${file.name}"
                }

                when (chunkId) {
                    "fmt " -> {
                        require(chunkLength >= MIN_FMT_BYTES) {
                            "Short fmt chunk in ${file.name}"
                        }
                        audioFormat = readUInt16Le(wav)
                        channelCount = readUInt16Le(wav)
                        sampleRate = readUInt32Le(wav).toInt()
                        readUInt32Le(wav) // Byte rate.
                        readUInt16Le(wav) // Block alignment.
                        bitsPerSample = readUInt16Le(wav)
                    }

                    "data" -> {
                        dataOffset = chunkStart
                        dataLength = chunkLength
                    }
                }

                wav.seek(chunkEnd + (chunkLength and 1L))
            }

            require(audioFormat == PCM_FORMAT) { "Only integer PCM WAV is supported: ${file.name}" }
            require(channelCount == MONO_CHANNELS) { "WAV must be mono: ${file.name}" }
            require(bitsPerSample == PCM16_BITS) { "WAV must be PCM16: ${file.name}" }
            val rate = requireNotNull(sampleRate) { "Missing fmt chunk: ${file.name}" }
            require(rate > 0) { "Invalid sample rate: ${file.name}" }
            val offset = requireNotNull(dataOffset) { "Missing data chunk: ${file.name}" }
            val byteCount = requireNotNull(dataLength) { "Missing data chunk: ${file.name}" }
            require(byteCount > 0L && byteCount % BYTES_PER_SAMPLE == 0L) {
                "Invalid PCM data length: ${file.name}"
            }
            require(byteCount / BYTES_PER_SAMPLE <= Int.MAX_VALUE) {
                "WAV is too large: ${file.name}"
            }

            wav.seek(offset)
            val samples = FloatArray((byteCount / BYTES_PER_SAMPLE).toInt())
            for (index in samples.indices) {
                val low = wav.readUnsignedByte()
                val high = wav.readUnsignedByte()
                val signed = ((high shl 8) or low).toShort()
                samples[index] = signed / 32768.0f
            }
            return PcmAudio(samples, rate)
        }
    }

    private fun readFourCc(file: RandomAccessFile): String {
        val bytes = ByteArray(4)
        file.readFully(bytes)
        return String(bytes, StandardCharsets.US_ASCII)
    }

    private fun readUInt16Le(file: RandomAccessFile): Int {
        val low = file.readUnsignedByte()
        val high = file.readUnsignedByte()
        return low or (high shl 8)
    }

    private fun readUInt32Le(file: RandomAccessFile): Long {
        var result = 0L
        repeat(4) { shift ->
            result = result or (file.readUnsignedByte().toLong() shl (shift * 8))
        }
        return result
    }

    private const val CHUNK_HEADER_BYTES = 8L
    private const val MIN_FMT_BYTES = 16L
    private const val PCM_FORMAT = 1
    private const val MONO_CHANNELS = 1
    private const val PCM16_BITS = 16
    private const val BYTES_PER_SAMPLE = 2L
}
