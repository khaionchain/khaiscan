"""KhaiScan -- Report module."""
from report.formatter import build_report, build_lore_report, get_image_url
from report.image_renderer import render_report_image

__all__ = ["build_report", "build_lore_report", "get_image_url", "render_report_image"]
