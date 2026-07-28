# KhaiScan — Summary of Completed Updates

## 1. Smart Token Age Display
- **Sub-day precision**: Displays `<1d` or exact hours (`1h` - `23h`) if created less than 24 hours ago using raw creation timestamps (`created_at_ts`).
- **Standardized formatting**: Shows `Xd` (days), `Xmo` (months), or `X.Xy` / `Xy` (years) across both the image report and text report.

## 2. Gemini Removal
- Completely removed Google Gemini Flash dependency from `ai/lore.py`.
- **Groq primary engine**: `GROQ_API_KEY` (Groq free tier) is now the sole AI provider for narrative analysis.
- Updated startup config warnings to point to Groq (`console.groq.com/keys`).

## 3. High Definition Image + Grouped Text Delivery
- **3x Ultra HD scale**: Rendered via Playwright with `device_scale_factor=3` for ultra-sharp clarity on retina and high-DPI displays.
- **Grouped Telegram output**: The report image is sent directly as a photo, and the full text report is attached immediately as a reply to it so both appear together cleanly in chat.

## 4. Bundle Activity Data Fix
- Display `bundle_pct` directly whenever available from RugCheck, GMGN, or InsightX, even if the rules engine threshold doesn't emit a separate verdict.

## 5. Fraud & Fake Activity Detection
- Created `scanner/fake_detector.py` to detect suspicious on-chain patterns using collected data:
  - **Fake / Wash Volume**: Flags abnormal Volume/Market Cap ratios (>5x or >10x) or volume exceeding 20x pool liquidity.
  - **Airdropped Supply**: Detects dust distribution / holder count inflation based on MC-per-holder heuristics and risk flags.
  - **Suspicious Buys**: Flags high bundling (>20%) or coordinated insider buy patterns.
- Fraud warnings automatically appear at the top of the **Risk Flags** section in both the image and text reports.
