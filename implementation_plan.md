# KhaiScan — Image-Based Report UI Overhaul

The current bot sends reports as **plain HTML text** in Telegram. The target UI (from the screenshot) is a rich, dark-themed **card-based dashboard image**. Since Telegram's HTML renderer is extremely limited (no CSS, no layout), the only way to match this design is to **render the report as an image** (PNG) and send it as a photo.

## Approach: HTML → Image Rendering with Playwright

We'll create an HTML template styled with CSS that replicates the screenshot's dark card-based UI, then render it to a PNG image using **Playwright** (headless Chromium). This is a well-established pattern for Telegram bots that need rich visuals.

> [!IMPORTANT]
> This adds `playwright` as a dependency (~50MB download for the browser binary). This is the standard approach for image-rendered bot reports. Alternatives like `Pillow` (manual pixel drawing) would be far more complex and harder to maintain.

## Proposed Changes

### New: Image Renderer Module

#### [NEW] [image_renderer.py](file:///Users/savvy/Desktop/khaiscan/report/image_renderer.py)

A new module that:
1. Takes a `ScanResult` and fills an HTML template with the data
2. Uses Playwright to screenshot the HTML into a PNG `bytes` buffer
3. Returns the PNG bytes ready to send via Telegram's `send_photo`

The HTML template will replicate every section from the screenshot:
- **Header bar** — KhaiScan logo text, "AI-Powered Token Intelligence", admin badge, timestamp
- **Token identity card** — Symbol, name, chain badge, age badge, DEGEN SCORE dial, coverage badge, scanned-by badge
- **Stat ribbon** — Price, Market Cap, Liquidity, 24h Volume, Holders (horizontal icons)
- **Health Overview** — Score gauge (64/100), color legend, category bars with emoji + score
- **Basic Information** — Key/value table with token image
- **Security** — Row-by-row verdicts with colored dots
- **Launch Analysis** — Bundle activity, insider wallets
- **Holder Analysis** — Top 10, largest wallet, LP lock, bundle, InsightX link
- **Developer Analysis** — Dev holdings, dev sold
- **Market Activity** — Volume/MC, Liquidity/MC with colored dots
- **Smart Money** — Smart wallets, net bias
- **Lore** — One-line summary, narrative/originality/virality gauges, lore score, comps
- **Risk Flags** — Checkmark or list of flags
- **Decision Engine** — Score bar with gradient (red → yellow → green), verdict label
- **Why This Score?** — Category score badges, strengths list, risks list
- **Summary** — Verdict + lore note
- **Footer** — "KhaiScan · Powered by Gemini Flash"

#### [NEW] [template.html](file:///Users/savvy/Desktop/khaiscan/report/template.html)

A Jinja2 HTML template with embedded CSS that implements the dark-themed card design. Key design tokens:
- Background: `#0a0e1a` (deep navy)
- Card backgrounds: `#141828` with `1px solid #1e2640` borders, `border-radius: 12px`
- Accent color: `#00e5ff` (cyan) for highlights
- Score colors: green `#00e676`, yellow `#ffc107`, orange `#ff9800`, red `#f44336`
- Font: Inter (loaded via Google Fonts)
- Width: 500px (optimal for Telegram photo display)

---

### Modified: Report Formatter

#### [MODIFY] [formatter.py](file:///Users/savvy/Desktop/khaiscan/report/formatter.py)

- Add a new public function `build_image_report(result: ScanResult) -> bytes` that calls the image renderer
- Keep `build_report()` as a **fallback** for text-only mode (if image rendering fails)
- Keep `build_lore_report()` unchanged (text is fine for lore-only)

---

### Modified: Bot Handlers

#### [MODIFY] [handlers.py](file:///Users/savvy/Desktop/khaiscan/bot/handlers.py)

- Update `_run_scan()` to:
  1. Generate the image report via `build_image_report()`
  2. Send it as a photo using `bot.send_photo()` with the image bytes
  3. Fall back to the existing text report if image generation fails
- Remove the separate `_try_send_photo()` for the token PFP (the token image is now embedded in the report image itself)

---

### Modified: Dependencies

#### [MODIFY] [requirements.txt](file:///Users/savvy/Desktop/khaiscan/requirements.txt)

Add:
```
playwright==1.52.0
jinja2==3.1.6
```

> [!NOTE]
> After installing, `playwright install chromium` must be run once to download the browser binary.

---

### Report `__init__`

#### [MODIFY] [__init__.py](file:///Users/savvy/Desktop/khaiscan/report/__init__.py)

Export the new `build_image_report` function.

## Verification Plan

### Manual Verification
1. Run the bot locally in polling mode
2. Send a known Solana token address (e.g., $ROCK or any popular memecoin)
3. Verify the bot sends a premium dark-themed image report matching the screenshot layout
4. Verify the image is readable on both mobile and desktop Telegram clients
5. Verify text fallback works if Playwright is unavailable

### Automated Tests
```bash
cd /Users/savvy/Desktop/khaiscan && python -m pytest tests/ -v
```
- Add a test that creates a `ScanResult` with mock data and verifies `build_image_report()` returns valid PNG bytes
