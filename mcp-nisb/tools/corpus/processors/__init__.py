#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Corpus Ingest Processors
处理器模式 - 支持多种入库方式
"""

from .base import BaseProcessor, auto_detect_processor
from .direct import DirectIngestProcessor
from .staging import StagingIngestProcessor
from .guide import GuideProcessor
from .validation import ValidationProcessor

__all__ = [
    'BaseProcessor',
    'auto_detect_processor',
    'DirectIngestProcessor',
    'StagingIngestProcessor',
    'GuideProcessor',
    'ValidationProcessor'
]

