# Verification: Platform, Collection Path, and Local Runtime

Observed on 2026-07-30 KST.

## Platform facts checked directly

1. NAVER's [liability/legal notice](https://policy.naver.com/policy/disclaimer.html) says automated access or collection is prohibited except for explicitly permitted or pre-approved access, compliant API use, or access allowed by developer guidance/robots rules.
2. NAVER's [Blog data-transfer help](https://help.naver.com/service/5593/contents/15183?lang=ko&osType=COMMONOS) says Blog data transfer, backup, and transfer of ownership are unavailable even between same-name IDs.
3. NAVER's [Blog backup help](https://help.naver.com/service/5593/contents/15293?lang=ko&osType=PC) documents a different, owner-facing feature: directly authored posts can be saved as PDFs. It states 100 posts/PDF, 500 MB/PDF, 3 GB/day, and format/media limitations.
4. NAVER's [PDF-backup procedure](https://help.naver.com/service/5593/contents/15295?lang=ko&osType=PC) requires opening **My Blog management**, selecting posts, and creating/downloading the PDF. This is not an API archive endpoint.
5. `https://blog.naver.com/robots.txt` was directly observed by the Naver-access worker to contain AI-training/RAG-specific disallow language. This evidence supports a no-automation default but does not by itself decide contract, copyright, or consent questions.

## Local-runtime check

The planned `tars` host could not be inspected on 2026-07-30 because the local SSH client rejects `/etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf`: both it and its target currently have owner `nobody:nogroup` rather than the expected system owner. No workaround or system change was applied because runtime inspection is outside this research scope.

The implementation recommendation therefore does not depend on unverified RAM/model-size claims. Apple documents [PyTorch MPS acceleration on Apple silicon](https://developer.apple.com/metal/pytorch/), while [Ollama macOS requirements](https://docs.ollama.com/macos) and [llama.cpp](https://github.com/ggml-org/llama.cpp) document Apple M-series/Metal support. Exact local model selection remains a benchmark gate after remote access is repaired.

## Verdict

- **Autonomous Blog corpus crawler:** blocked by policy evidence unless NAVER provides explicit permission for the exact endpoint, cadence, storage, and AI purpose.
- **Consenting owner's input package:** viable via the owner-facing PDF backup flow and, preferably, original source files outside NAVER.
- **Local RAG prototype on M3 Pro:** technically plausible, but model-size and latency targets are unverified until RAM and runtime benchmarks are measured on `tars`.
