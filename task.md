# KhaiScan Image Report — Tasks

## Phase 1: Core Image Renderer (Complete)
- `[x]` Update requirements.txt (add playwright, jinja2)
- `[x]` Create HTML template (report/template.html)
- `[x]` Create image renderer module (report/image_renderer.py)
- `[x]` Update report/__init__.py exports
- `[x]` Update bot/handlers.py — send image reports
- `[x]` Install dependencies & run playwright install chromium
- `[x]` Test end-to-end (generate test image)

## Phase 2: Polish to Match Sample Image (Complete)
- `[x]` Add "New!" badge next to age when token age is 0 days
- `[x]` Add 📋 copy icon after contract address
- `[x]` Add "/100" sub-text inside health gauge ring
- `[x]` Enlarge gauge ring for cleaner text fit (74px → 84px)
- `[x]` Fix security score threshold (67 → 75) for "GOOD" status in test data
- `[x]` Regenerate test image — verified match with sample screenshot
