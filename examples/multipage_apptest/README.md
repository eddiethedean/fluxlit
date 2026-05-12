# Multipage AppTest Demo

This example shows a FluxLit app with two pages and stable widget keys that can be
smoke-tested with Streamlit `AppTest`.

```bash
fluxlit dev examples.multipage_apptest.app:app
```

For Pytest, use FluxLit's bundled Streamlit entrypoint rather than importing
`fluxlit.streamlit.main` directly:

```python
from streamlit.testing.v1 import AppTest

from fluxlit import streamlit_main_path


def test_home(monkeypatch):
    monkeypatch.setenv("FLUXLIT_APP", "examples.multipage_apptest.app:app")
    monkeypatch.setenv("FLUXLIT_TESTS", "1")
    at = AppTest.from_file(str(streamlit_main_path())).run()
    assert at.title and at.title[0].value == "Home Page"
```

Keep multipage AppTest checks thin: assert that each important page can render, then
cover table mutations and navigation-heavy flows with API tests or browser E2E.
