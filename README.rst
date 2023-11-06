RPM Spec File Language Server
=============================

Requirements
------------

- Python >= 3.11
- `poetry <https://python-poetry.org/>`_


Running the server
------------------

- Install the dependencies via :command:`poetry install`
- Launch the server in tcp mode (binds to ``127.0.0.1:2087`` by default) via
  :command:`python3 -mrpm_spec_language_server --tcp`


Clients
=======


VSCode
------

A very simple VSCode client is available in ``clients/vscode/``. Building
requires nodejs and the :command:`npm` package manager:

.. code-block:: shell-session

   $ npm install
   $ npm run package


Install the created :file:`rpm-spec-language-server-$VERSION.vsix` and launch
the language server in tcp mode.

vis with [vis-lspci](https://gitlab.com/muhq/vis-lspc)
------------------------------------------------------

Add to your `~/.config/vis/visrc.lua` this code:

.. code-block:: lua

    lsp = require('plugins/vis-lspc')
    lsp.logging = true
    lsp.highlight_diagnostics = true
    lsp.ls_map['rpmspec'] = {
        name = 'RPMSpec',
        cmd = 'python3 -mrpm_spec_language_server --tcp'
    }
