RPM Spec File Language Server
=============================


.. |CI Status| image:: https://github.com/dcermak/rpm-spec-language-server/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/dcermak/rpm-spec-language-server/actions/workflows/ci.yml

.. |VSCode CI Status| image:: https://github.com/dcermak/rpm-spec-language-server/actions/workflows/vscode-extension.yml/badge.svg
   :target: https://github.com/dcermak/rpm-spec-language-server/actions/workflows/vscode-extension.yml

.. |Code Coverage| image:: https://codecov.io/gh/dcermak/rpm-spec-language-server/graph/badge.svg?token=HN0KY22PM1
   :target: https://codecov.io/gh/dcermak/rpm-spec-language-server

This is a proof of concept implementation of a server implementing the `Language
Server Protocol <https://microsoft.github.io/language-server-protocol/>`_ for
RPM Spec files.

Please share your feature requests with us by opening an `issue
<https://github.com/dcermak/rpm-spec-language-server/issues/new/choose>`_,
creating a `discussion
<https://github.com/dcermak/rpm-spec-language-server/discussions/new/choose>`_
or chat with us on matrix in `#rpm-spec-language-server:matrix.org
<https://matrix.to/#/%23rpm-spec-language-server%3Amatrix.org?via=matrix.org&via=one.ems.host>`_.


Supported LSP endpoints
-----------------------

- autocompletion of macro names, spec sections and preamble keywords
- jump to macro definition
- expand macros on hover
- breadcrumbs/document sections


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

The server requires the `spec.md
<https://raw.githubusercontent.com/rpm-software-management/rpm/master/docs/manual/spec.md>`_
file. It can either use the locally installed copy from the ``rpm`` package or
(if the documentation has not been installed) from a locally cached version in
``~/.cache/rpm/spec.md``.


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
    lsp.ls_map['rpmspec'] = {
        name = 'RPMSpec',
        cmd = 'python3 -mrpm_spec_language_server --stdio'
    }

Neovim with built-in LSP client
-------------------------------

.. code-block:: lua

    local nvim_lsp = require('lspconfig')

    require('lspconfig.configs').rpmspec = {
        default_config = {
          cmd = { 'python3', '-mrpm_lsp_server', '--stdio' },
          filetypes = { 'spec' },
          single_file_support = true,
          root_dir = util.find_git_ancestor,
          settings = {},
        },
        docs = {
          description = [[
      https://github.com/dcermak/rpm-spec-language-server

      Language server protocol (LSP) support for RPM Spec files.
      ]],
        },
    }

    nvim_lsp['rpmspec'].setup({})
