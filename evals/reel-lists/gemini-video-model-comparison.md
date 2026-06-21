# Gemini Video Model Comparison Reel Lists

Saved on 2026-06-21 for comparing `gemini-2.5-flash` and `gemini-2.5-flash-lite` on real Instagram Reel extraction.

URL-only fixtures:

- `evals/reel-lists/gemini-video-smoke-4.txt`
- `evals/reel-lists/gemini-video-comparison-20.txt`

## Four-Reel Smoke Set

- https://www.instagram.com/reel/DVvk5NzjJj6/?igsh=MW9lc2wwejJkMGNweg==
- https://www.instagram.com/reel/DR5nms0gXZ1/?igsh=dDM5dzl0NGRzcWZj
- https://www.instagram.com/reel/DW9GWYTjOqx/?igsh=ZTJpZml0MDhmdTll
- https://www.instagram.com/reel/DVqsAbKjOcX/?igsh=c3Q3cTdyaWgzbTdr

## Twenty-Reel Comparison Set

- https://www.instagram.com/reel/DZU1t7hSRI6/?igsh=MTEwMHE2bXhrOHpqcQ==
- https://www.instagram.com/reel/DZdUAaeMDDJ/?igsh=OTc5MDdza3k0NGgy
- https://www.instagram.com/reel/DXMZVb0kaNM/?igsh=MXJ3YnJkNXd1ZzcydA==
- https://www.instagram.com/reel/DZkPiNyh5Tm/?igsh=MW91ZHZmaDBhenFuaQ==
- https://www.instagram.com/reel/DZeWnNxSanY/?igsh=OXhnd21wY3Z1eXM0
- https://www.instagram.com/reel/DYpFwvPyFUl/?igsh=MXAyM2ZwOWE2ZmZ4ZA==
- https://www.instagram.com/reel/DZtUCZTyyTX/?igsh=MWw0NGEyanVncHNwcA==
- https://www.instagram.com/reel/DY1eDeHOvo2/?igsh=dXMwOThjY3N2OHd5
- https://www.instagram.com/reel/DXhRO5FEiHE/?igsh=eno2bGZuajFpaThs
- https://www.instagram.com/reel/DZvG5VvIhOX/?igsh=MTJndTRscjQ2ZWxoMg==
- https://www.instagram.com/reel/DXHVaphjDA7/?igsh=N2lrd2I0MDZwYW1v
- https://www.instagram.com/reel/DYERlNXPsAU/?igsh=OGJmcGhscnF1MGZq
- https://www.instagram.com/reel/DXZZryJiL_p/?igsh=MWgzZ2ZkOXB1MG91Mg==
- https://www.instagram.com/reel/DYqJJb6v1Yy/?igsh=ZmFnbWtubHYxNXQ2
- https://www.instagram.com/reel/DZiKHY7sehK/?igsh=M2Vwa2FqNWRkYTJp
- https://www.instagram.com/reel/DYE-vLmMMR3/?igsh=NjRpMGZ5bGx4eXc=
- https://www.instagram.com/reel/DZxdHbeii8x/?igsh=MTdjZDB0ZDVoZzJyOQ==
- https://www.instagram.com/reel/DYNqhRHzPDT/?igsh=MXM0aWJ0NGRkZTI4aQ==
- https://www.instagram.com/reel/DZlB62Oxu8g/?igsh=NGM4a3R5aWdqY2Q5
- https://www.instagram.com/reel/DYfmsz4vdOo/?igsh=Z2MzZXpzdzZwdGM5

## Run Commands

Four-Reel smoke comparison:

```bash
python scripts/compare_gemini_video_models.py \
  --source-file evals/reel-lists/gemini-video-smoke-4.txt \
  --media-dir outputs/gemini-compare-smoke \
  --output outputs/gemini-compare-smoke/result.json
```

Twenty-Reel comparison:

```bash
python scripts/compare_gemini_video_models.py \
  --source-file evals/reel-lists/gemini-video-comparison-20.txt \
  --media-dir outputs/gemini-compare-20 \
  --output outputs/gemini-compare-20/result.json
```
