# S1-mini exact-checkpoint LiteRT-LM conversion

Date: 2026-08-22
Host: `dante` (`Linux 5.15.0-176-generic`, x86_64)
Run: `s1-mini-block32-ctx4096-20260822T062056Z`

## Outcome

The exact S1-mini BF16 checkpoint converted successfully to a 4,096-context LiteRT-LM bundle.
The retained artifact is 436,596,864 bytes with SHA-256
`8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403`.

Structural inspection passes. The bundle contains 1,154 INT4 tensors across its main-model and
embedder TFLite sections. Every INT4 tensor uses `BlockwiseQuantization` with block size 32, every
referenced scale tensor is FLOAT16, and every KV-cache signature tensor is FLOAT32. No channelwise,
block-64/block-128, or sub-four-bit arm was produced.

This is conversion plus initial host-runtime evidence, not a runtime-selection result. LiteRT-LM
JVM 0.16.1 loaded the exact artifact on both CPU and GPU, rendered the frozen S1 cleanup prompt
byte-for-byte, and produced the same `Hello there` response for the project-authored
`um hello there` smoke. No Pixel measurement has occurred. Tuned LEAP remains production.

## Source gate

The source directory was transferred outside Git and verified before package installation or
conversion. It contains exactly the 12 files declared by the conversion manifest.

- Model: `S1-mini by Superwhisper`
- Revision: `65f84bcda1d13df582c4a8443c1c5aa53c0c66db`
- `model.safetensors`: 1,503,300,328 bytes; SHA-256
  `69d2057077ab4dc738aaaab75d2a8ffa141e3a09fb9d956198cfce46f381131a`
- `tokenizer.json`: 11,422,654 bytes; SHA-256
  `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4`
- `chat_template.jinja`: 4,168 bytes; SHA-256
  `a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8`
- Source preflight report SHA-256:
  `38776a34c0594886703556060c2b52ed8c188357ff0e8a3328d45f18fb9a664d`

The GGUF, generic Qwen weights, evaluation corpora, expected outputs, prior model outputs, and
private transcripts were not used.

## Conversion contract

- Python `3.11.14`
- `litert-torch==0.9.3`
- `ai-edge-quantizer==0.8.0`
- `ai-edge-litert==2.1.6`
- `litert-converter==0.3.1`
- `litert-lm-builder==0.16.1`
- Recipe: `dynamic_wi4b32_afp32`
- Weights: symmetric INT4, `BLOCKWISE_32`
- Activations: FLOAT32; KV cache: FLOAT32
- Integer compute, no explicit dequantize, no calibration
- Cache length: 4,096
- Prefill shapes: 128, 256, 512, 1,024, and 1,152
- External embedder: enabled
- Temporary TFLite sections: retained for inspection

`ai-edge-litert==2.1.6` leaves `backports-strenum` unconstrained. The initial lock selected 1.3.1,
whose own metadata intentionally excludes Python 3.11. The final lock pins 1.2.8, the last release
declaring Python 3.11 support. After that correction, all 85 installed packages passed `uv pip
check`. The final 85-line environment freeze has SHA-256
`f9bc6e4fa53c6b9176b53d2a472b2d2a8caa824ec6cc76268c64c9bae5acfe99`.

Primary references:

- [Official LiteRT Torch generative conversion guide](https://developers.google.com/edge/litert/conversion/pytorch/genai)
- [LiteRT Torch v0.9.3 source](https://github.com/google-ai-edge/litert-torch/tree/v0.9.3)
- [Python-3.11-compatible backports.strenum 1.2.8 metadata](https://pypi.org/project/backports.strenum/1.2.8/)
- [LiteRT-LM Kotlin API](https://github.com/google-ai-edge/LiteRT-LM/blob/main/docs/api/kotlin/getting_started.md)

## Execution evidence

The run started at `2026-08-22T06:22:10.357292+00:00` and completed at
`2026-08-22T06:27:56.490968+00:00` with exit status 0. Dante had approximately 120 GiB available
RAM and 9.3 TB available disk at launch. The exporter loaded the checkpoint, emitted all five
prefill programs and decode, lowered and merged their MLIR, ran LiteRT converter passes, quantized
the main model and external embedder, exported the tokenizer, and packaged the bundle.

The conversion stack emitted a PyTorch warning that Dante's NVIDIA driver was older than the
installed CUDA 13 build. Torch nevertheless held the model on the A6000 while JAX explicitly used
CPU for MLIR module creation. This did not change the artifact contract or produce an exporter
error. It is recorded as conversion-host behavior and makes no claim about Pixel runtime backend.

Intermediate retained sizes on Dante:

| File | Bytes |
|---|---:|
| `model.tflite` | 2,394,761,376 |
| `model_quantized.tflite` | 346,893,024 |
| `embedder.tflite` | 622,333,828 |
| `embedder_quantized.tflite` | 87,519,360 |
| `model.litertlm` | 436,596,864 |

The official `litert-lm-peek` tool reports bundle version 1.6.0, four sections, Qwen3 model
metadata, 4,096 maximum tokens, stop token IDs 151643/151645, and the embedded source Jinja
template. The template includes the exact `enable_thinking=false` assistant prefix path.

## Host runtime smoke

An isolated Kotlin/JVM probe pins `com.google.ai.edge.litertlm:litertlm-jvm:0.16.1`. It verifies
the artifact byte size and SHA-256 before load, uses context 4,096, greedy sampling
(`topK=1`, `topP=1`, `temperature=0`), `ThinkingConfig(false)`, and
`extraContext={enable_thinking:false}`. It refuses generation unless the runtime-rendered prompt
exactly matches the frozen system/control/Qwen template bytes.

The authored raw text `um hello there` is 3 source-tokenizer tokens. Both host arms therefore used
an 81-token expected prompt and the product output cap of 36. The rendered prompt was 404 UTF-8
bytes at SHA-256 `0b546eb4a221629272391b80cbf55e5cf26af3f9ff9df2305923d1362b4c99fb`.

| Host arm | Load wall time | Generation wall time | Raw response | Result report SHA-256 |
|---|---:|---:|---|---|
| CPU, 2 threads | 1.768 s | 2.647 s | `Hello there` | `51b00827ab6022cb8a20ba4ee2ec27dc6bc6de5b032b43e8a6b44f0df93ebb9c` |
| Apple M2 GPU / WebGPU | 3.258 s | 0.792 s | `Hello there` | `93ba99ad8ef542512a17cbb4a3a929f06ca6f2b951cad922bdfb026ddedd9a82` |

These one-shot Mac wall times are smoke evidence only and are not comparable to Pixel LEAP.
LiteRT-LM's published JVM configuration did not enable native benchmark counters, so the probe
records the explicit benchmark-unavailable error rather than inventing TTFT/token-rate values.
GPU logs identify Apple M2/Metal WebGPU delegation; the missing optional WebGPU sampler library
caused only the sampler to fall back to the statically linked implementation. CPU logs identify
XNNPACK. Both engines closed cleanly. No evaluation corpus, expected output, private transcript,
microphone, ADB, or Pixel was used.

## Structural inspection

| Bundle section | Role | INT4 tensors | Block-32 tensors | Scale tensors |
|---:|---|---:|---:|---|
| 2 | prefill/decode model | 1,152 | 1,152 | 1,152 FLOAT16 |
| 3 | external embedder | 2 | 2 | 2 FLOAT16 |

All named `kv_cache_*` signature inputs and outputs were checked as FLOAT32. Integer token IDs are
expected. The inspection report verdict is `pass`; its SHA-256 is
`d5a09a89f7b25f6bac63879462e1b2e5b3ed19588cbfe4d416e7e3e64f931b7b`.

## Reproducibility identities

| Item | SHA-256 |
|---|---|
| Conversion config | `8b3e3fa25f33d25fb07102a26fe6221cebccbfe7f7bed38f891a1b4e211a7ef7` |
| Resolved recipe | `adb077a5b1cc04af108cf9c27f6555f5d71fe67b773b53741490f32a167598ba` |
| `conversion/pyproject.toml` | `99050e605c530be48537279559a861ae5580d0418dd854e8628843a1c2b1513e` |
| `conversion/uv.lock` | `af2697f49296bb16c0cf4d7ae2c2545353297681bf08094e001e93b50791b4f9` |
| Export status | `6450e5d050d04a368abf4efb004535c8d4d082cfa877331fcbabd99d7f3f166d` |
| Export log | `03c8d8ab5b21042fcb600a92ff1c10d28d606263debd97b24e2118ce531fbd8a` |
| Final `.litertlm` | `8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403` |

Weights, the final bundle, intermediates, reports, and logs remain outside Git. The final artifact
and small reports are mirrored under ignored local path
`.cache/integration/s1-mini-litert-v1/20260822T062056Z/`; the complete intermediates remain under
`/data/rise/android_stt/litert-conversion/` on Dante.

## Pixel follow-up

The isolated Android follow-up is complete. On the frozen English user-shaped fixture, LiteRT CPU
and fully delegated Mali/OpenCL GPU both lost 10/10 paired total-latency comparisons against tuned
LEAP and materially regressed PSS. Stage 3 stopped before sustained/power work and retained LEAP.
See `docs/evaluation/results/2026-08-22-s1-mini-litert-pixel.md`.
