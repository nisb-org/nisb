#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass
from typing import Tuple


@dataclass
class PDFStyleConfig:
    """PDF 样式配置"""

    # 页面底色（米黄色）
    page_bg_color: Tuple[float, float, float] = (0.988, 0.976, 0.953)

    # 批注卡片样式
    annotation_card_bg: Tuple[float, float, float] = (0.985, 0.973, 0.947)
    annotation_bar_color: Tuple[float, float, float] = (0.77, 0.47, 0.20)
    annotation_title_color: Tuple[float, float, float] = (0.32, 0.23, 0.16)
    annotation_body_color: Tuple[float, float, float] = (0.20, 0.18, 0.16)

    # 页眉装饰线
    header_decoration_color: Tuple[float, float, float] = (0.77, 0.47, 0.20)
    header_decoration_width: float = 0.8

    # 页码颜色
    footer_text_color: Tuple[float, float, float] = (0.45, 0.42, 0.38)

    # 正文颜色
    body_text_color: Tuple[float, float, float] = (0, 0, 0)

    # 开关
    enable_page_background: bool = True
    enable_header_decoration: bool = True
    enable_paragraph_spacing: bool = True
    enable_annotation_card_style: bool = True

