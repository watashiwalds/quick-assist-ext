# So sánh tổ hợp model

> Chỉ so sánh trong cùng nhóm `(dataset_fingerprint, top_k, max_sources, modules, evidence_type)`.
> Run smoke/khác cấu hình được tách nhóm thay vì trộn vào một bảng.
> Chỉ số PageMatch chính là `PM Hit@all`, `PM vRecall`, `PM vFPR` (chấm trên mọi item trả về / item `verified`). `PM Hit (seg)` và `PM FPR (seg)` giữ nghĩa cũ để đối chiếu lịch sử.

## Nhóm `4e6fa6ea3cfebd2c` · top_k=5 · max_sources=5 · modules=search,rag,pagematch · evidence=smoke

| Model combo | Run | Search n | R@k | MRR | RAG n | Token-F1 | RAG p50 (ms) | Từ chối đúng | PM Hit@all | PM vRecall | PM vFPR | PM Hit (seg) | PM FPR (seg) | Tokens |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `smoke-api-check` | 20261119_042408_020707_smoke-api-check_api-check | 1 | 1.0 | 1.0 | 1 | 0.4918 | 2270.04 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 8728 |
| `smoke-api-check` | 20261119_042903_488892_smoke-api-check_final | 1 | 1.0 | 1.0 | 1 | 0.4154 | 2105.94 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 8708 |

## Nhóm `ef7c82ca643482ab` · top_k=5 · max_sources=5 · modules=search,rag,pagematch · evidence=quality

| Model combo | Run | Search n | R@k | MRR | RAG n | Token-F1 | RAG p50 (ms) | Từ chối đúng | PM Hit@all | PM vRecall | PM vFPR | PM Hit (seg) | PM FPR (seg) | Tokens |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4` | 20261119_045531_300530_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4` | 20261119_045729_886201_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local | 38 | 0.7105 | 0.6798 | 38 | 0.1707 | 2902.88 | 1.0 | 0.8421 | 0.8421 | 0.7273 | 0.8235 | 0.6667 | 491542 |
| `local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4` | 20261119_173736_232665_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_lat3-full-local | 38 | 0.7105 | 0.6798 | 38 | 0.1694 | 3782.71 | 0.9091 | 0.6316 | 0.5789 | 0.5455 | 0.6 | 0.3333 | 442183 |
| `local-qwenternary-qwenqte` | 20261121_023251_415228_local-qwenternary-qwenqte_lat3-full-local | 38 | 0.7105 | 0.6798 | 38 | 0.1629 | 3332.26 | 0.8182 | 0.7895 | 0.7632 | 0.6364 | 0.7895 | 0.5 | 588953 |
| `gemma-4-31b-it+gemini-emb` | 20261121_024136_851783_gemma-4-31b-it-gemini-emb_eval-gemini-20261121 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `gemma-4-31b-it+gemini-emb` | 20261121_024854_536342_gemma-4-31b-it-gemini-emb_eval-gemini-retry-01 | 38 | 1.0 | 0.9868 | 15 | 0.2251 | 21526.85 | 0.75 | 0.2368 | 0.0 | 0.0 | — | — | 239470 |
| `local-qwenternary-qwen3embed` | 20261121_030233_051040_local-qwenternary-qwen3embed_lat3-full-local | 38 | 0.9737 | 0.9342 | 38 | 0.177 | 2645.19 | 0.8182 | 0.7632 | 0.6842 | 0.4545 | 0.5714 | 0.5 | 561371 |
| `gemma-4-31b-it+gemini-emb` | 20261121_035553_459258_gemma-4-31b-it-gemini-emb_eval-gemini-fresh-01 | 38 | 1.0 | 0.9868 | 11 | 0.1993 | 24013.64 | 1.0 | 0.5 | 0.0 | 0.0 | 0.0 | — | 288221 |
| `local-qwen3.5_4b-qwen3embed` | 20261121_043458_145357_local-qwen3-5-4b-qwen3embed_lat3-full-local | 38 | 0.9737 | 0.9342 | 38 | 0.1638 | 4952.55 | 0.6364 | 0.6579 | 0.6316 | 0.3636 | 0.5938 | 0.3 | 562444 |
| `local-qwen3.5_4b-qwengte` | 20261121_050139_470458_local-qwen3-5-4b-qwengte_lat3-full-local | 38 | 0.7105 | 0.6798 | 38 | 0.1493 | 4341.97 | 0.8182 | 0.6842 | 0.6579 | 0.5455 | 0.5862 | 0.5 | 586791 |

## Nhóm `e342658c42ad9b4c` · top_k=5 · max_sources=5 · modules=search,rag · evidence=smoke

| Model combo | Run | Search n | R@k | MRR | RAG n | Token-F1 | RAG p50 (ms) | Từ chối đúng | PM Hit@all | PM vRecall | PM vFPR | PM Hit (seg) | PM FPR (seg) | Tokens |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `smoke-lat3` | 20261119_172442_392982_smoke-lat3_mini | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `smoke-lat3` | 20261119_173634_531332_smoke-lat3_mini2 | 2 | 0.0 | 0.0 | 2 | 0.4658 | 1486.93 | 1.0 | — | — | — | — | — | 3733 |
| `smoke-lat3` | 20261119_173710_074920_smoke-lat3_mini3 | 2 | 1.0 | 1.0 | 2 | 0.3872 | 639.97 | 1.0 | — | — | — | — | — | 3756 |
