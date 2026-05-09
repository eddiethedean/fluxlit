# Python API reference

Generated from docstrings with Sphinx autodoc. Public modules:

```{eval-rst}
.. automodule:: fluxlit
   :members:
   :show-inheritance:

.. automodule:: fluxlit.app
   :members:
   :show-inheritance:

.. automodule:: fluxlit.client
   :members:
   :show-inheritance:

.. automodule:: fluxlit.config
   :members:
   :show-inheritance:

.. automodule:: fluxlit.project_config
   :members:
   :show-inheritance:

.. automodule:: fluxlit.logging_context
   :members:
   :show-inheritance:

.. automodule:: fluxlit.gateway
   :members:
   :show-inheritance:

.. automodule:: fluxlit.runtime
   :members:
   :show-inheritance:

.. automodule:: fluxlit.testing
   :members:
   :show-inheritance:

.. automodule:: fluxlit.api
   :members:
   :show-inheritance:

.. automodule:: fluxlit.auth
   :members:
   :show-inheritance:

.. automodule:: fluxlit.page
   :members:
   :show-inheritance:
```

The Typer CLI module ({mod}`fluxlit.cli`) is primarily used via the `fluxlit` console script; its objects are listed below for completeness.

```{eval-rst}
.. automodule:: fluxlit.cli
   :members:
   :show-inheritance:
```

The Streamlit entry script **`fluxlit.streamlit_main`** is executed by `streamlit run` with `FLUXLIT_APP` set. It is not import-safe for autodoc (module-level initialization). See the source file `streamlit_main.py` in the repository.
