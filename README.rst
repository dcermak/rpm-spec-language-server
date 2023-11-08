RPM Spec File Language Server
=============================

Requirements
------------

- Python >= 3.11
- `poetry <https://python-poetry.org/>`_


Running the server
------------------

- Install the dependencies via ``poetry install``
- Launch the server in tcp mode (binds to ```127.0.0.1:2087`` by default) via
  ``poetry run rpm_lsp_server``

Alternatively, you can build the python package, install the wheel and run the
module directly:

.. code-block:: shell-session

   poetry build
   pip install --user dist/rpm_spec_language_server-*.whl
   python -m rpm_spec_language_server


Clients
=======


VSCode
------

A very simple VSCode client is available in ``clients/vscode/``. Building
requires nodejs and the ``npm`` package manager:

.. code-block:: shell-session

   $ npm install
   $ npm run package


Install the created ``rpm-spec-language-server-$VERSION.vsix`` and launch
the language server in tcp mode.


vis with `vis-lspci <https://gitlab.com/muhq/vis-lspc>`_
--------------------------------------------------------

Add to your `~/.config/vis/visrc.lua` this code:

.. code-block:: lua

    lsp = require('plugins/vis-lspc')
    lsp.logging = true
    lsp.highlight_diagnostics = true
    lsp.ls_map['rpmspec'] = {
        name = 'RPMSpec',
        cmd = 'python3 -mrpm_spec_language_server'
    }


Neovim with built-in LSP client
-------------------------------

.. code-block:: lua

    local nvim_lsp = require('lspconfig')

    require('lspconfig.configs').rpmspec = {
        default_config = {
            cmd = {'rpm_lsp_server', '--verbose',
                   '--log_file', vim.fn.stdpath('state') .. '/rpm_spec_lsp-log.txt'},
            filetypes = {'spec'},
            single_file_support = true,
            settings = {},
        }
    }

    nvim_lsp['rpmspec'].setup({})
