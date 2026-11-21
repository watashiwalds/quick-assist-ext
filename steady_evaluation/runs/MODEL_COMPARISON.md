# So sánh tổ hợp model

> Chỉ so sánh trong cùng nhóm `(dataset_fingerprint, top_k, max_sources, modules, evidence_type)`.
> Run smoke/khác cấu hình được tách nhóm thay vì trộn vào một bảng.
> Chỉ số PageMatch chính là `PM Hit@all`, `PM vRecall`, `PM vFPR` (chấm trên mọi item trả về / item `verified`). `PM Hit (seg)` và `PM FPR (seg)` giữ nghĩa cũ để đối chiếu lịch sử.

## Nhóm `ef7c82ca643482ab` · top_k=5 · max_sources=5 · modules=search,rag,pagematch · evidence=quality

| Model combo | Run | Search n | R@k | MRR | RAG n | Token-F1 | RAG p50 (ms) | Từ chối đúng | PM Hit@all | PM vRecall | PM vFPR | PM Hit (seg) | PM FPR (seg) | Tokens |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `gemma-4-31b-it+gemini-emb` | 20261121_024136_851783_gemma-4-31b-it-gemini-emb_eval-gemini-20261121 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `gemma-4-31b-it+gemini-emb` | 20261121_024854_536342_gemma-4-31b-it-gemini-emb_eval-gemini-retry-01 | 38 | 1.0 | 0.9868 | 15 | 0.2251 | 21526.85 | 0.75 | 0.2368 | 0.0 | 0.0 | — | — | 239470 |
| `gemma-4-31b-it+gemini-emb` | 20261121_035553_459258_gemma-4-31b-it-gemini-emb_eval-gemini-fresh-01 | 38 | 1.0 | 0.9868 | 11 | 0.1993 | 24013.64 | 1.0 | 0.5 | 0.0 | 0.0 | 0.0 | — | 288221 |
