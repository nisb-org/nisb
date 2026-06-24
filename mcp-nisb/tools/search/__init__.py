#!/usr/bin/env python3

from .cross_module import nisb_search_cross_module

__all__ = ["nisb_search_semantic", "nisb_search_cross_module"]


def nisb_search_semantic(*args, **kwargs):
    from .semantic import nisb_search_semantic as _impl
    return _impl(*args, **kwargs)

