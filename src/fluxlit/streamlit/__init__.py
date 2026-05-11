"""Streamlit integration: page config helpers and narrow typing facades.

Note: the Streamlit entrypoint module (:mod:`fluxlit.streamlit.main`) executes UI on import,
so it is intentionally **not** imported from this package initializer.
"""

from fluxlit.streamlit.facade import StreamlitSessionFacade
from fluxlit.streamlit.page import PageFn
from fluxlit.streamlit.page_config import build_set_page_config_kwargs

__all__ = [
    "PageFn",
    "StreamlitSessionFacade",
    "build_set_page_config_kwargs",
]
