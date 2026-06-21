# oMLX 模型清單

> 來源：`~/github/omlx/models.md`
> 服務端點：`http://127.0.0.1:11400/v1`
> 管理後台：`http://127.0.0.1:11400/admin/`

## Chat 模型

| 模型 | 來源 | 大小 | 用途 |
|------|------|------|------|
| **Qwen3-Coder-30B** | `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit` | 16.8 GB | 🏆 主力對話 |
| **Qwen3.5-0.8B-4bit** | `mlx-community/Qwen3.5-0.8B-4bit` | 0.6 GB | 輕量/分類 |
| **Llama-3.2-3B-Instruct-4bit** | `mlx-community/Llama-3.2-3B-Instruct-4bit` | 1.8 GB | 備用對話 |

## Vision 模型

| 模型 | 來源 | 大小 | 用途 |
|------|------|------|------|
| **GLM-OCR** 🏆 | `mlx-community/GLM-OCR-bf16` | 2.2 GB | **專用 OCR / 名片** |
| **Qwen2.5-VL-7B** | `mlx-community/Qwen2.5-VL-7B-Instruct-4bit` | 5.5 GB | 通用圖片理解 |
| **MiniCPM-V-4.6** | `mlx-community/MiniCPM-V-4.6-mxfp8` | 2.3 GB | 輕量 Vision（備用） |

## Embedding 模型

| 模型 | 來源 | 大小 | 維度 | API |
|------|------|------|------|-----|
| **bge-m3** | `mlx-community/bge-m3-mlx-fp16` | 1.1 GB | 1024 | `POST /v1/embeddings` |

## 服務管理

```bash
~/github/omlx/omlx.sh start|stop|restart|status|logs
```
開機自動啟動：✅ launchd
