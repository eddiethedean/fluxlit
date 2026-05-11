"""AppTest: URL-bound session survives a second run like a full refresh (Phase 2 follow-on)."""

from __future__ import annotations

import textwrap


def test_url_session_rehydrates_on_second_run_with_same_query_params(
    requires_streamlit_apptest,
) -> None:
    from streamlit.testing.v1 import AppTest

    script = textwrap.dedent(
        """
        import streamlit as st
        from fluxlit.url_session import (
            InMemorySessionStore,
            ensure_url_session,
            hydrate_url_session,
            persist_url_session,
        )

        _STORE = InMemorySessionStore(default_ttl_seconds=None)

        ensure_url_session(st, _STORE, param="fluxlit_sid")
        hydrate_url_session(st, _STORE, param="fluxlit_sid")

        if "wizard_step" not in st.session_state:
            st.session_state["wizard_step"] = 1

        st.text(f"wizard_step={st.session_state['wizard_step']}")
        persist_url_session(st, _STORE, param="fluxlit_sid")
        """
    )
    at = AppTest.from_string(script, default_timeout=10)
    at.run()
    assert at.text
    assert any("wizard_step=1" in t.value for t in at.text)

    del at.session_state["wizard_step"]
    at.run()
    assert any("wizard_step=1" in t.value for t in at.text)
