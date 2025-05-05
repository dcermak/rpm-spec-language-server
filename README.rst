RPM Spec File Language Server
=============================

|CI Status|  |VSCode CI Status|  |Code Coverage| |Chat on - Matrix|

.. |CI Status| image:: https://github.com/dcermak/rpm-spec-language-server/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/dcermak/rpm-spec-language-server/actions/workflows/ci.yml

.. |VSCode CI Status| image:: https://github.com/dcermak/rpm-spec-language-server/actions/workflows/vscode-extension.yml/badge.svg
   :target: https://github.com/dcermak/rpm-spec-language-server/actions/workflows/vscode-extension.yml

.. |Code Coverage| image:: https://codecov.io/gh/dcermak/rpm-spec-language-server/graph/badge.svg?token=HN0KY22PM1
   :target: https://codecov.io/gh/dcermak/rpm-spec-language-server

.. |Chat on - Matrix| image:: https://img.shields.io/static/v1?label=Chat+on&message=Matrix&color=#32c954&logo=Matrix
   :target: https://matrix.to/#/%23rpm-spec-language-server%3Amatrix.org?via=matrix.org&via=one.ems.host

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

- Python >= 3.9
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
``~/.cache/rpm/spec.md``. The language server will fetch the ``spec.md`` from
the upstream github repository if neither of the previous options works.


Container Mode
==============

The rpm-spec-language-server is a server that supports an **experimental**
container mode. In this mode, the server is launched inside a container with the
package directory mounted into the running container. This allows you to have
access to a different distribution than your current one.

The container mode can currently handle only having one package open. The RPM
spec file **must** be in the top-level directory. Additionally, the server
**must** communicate via TCP. This means that you might have to reconfigure your
lsp-client, if it assumes to communicate via stdio.

To run the language server in container mode, launch the language server with
the following additional flags:

.. code-block:: shell-session

   $ cd ~/path/to/my/package
   $ # ensure that the spec file is in the current working directory!
   $ python -m rpm_spec_language_server -vvv \
         --distribution $distri \
         --container-mode \
         --container-runtime=$runtime \

where you replace ``$distri`` with one of ``tumbleweed``, ``leap-15.5``,
``leap-15.6``, ``fedora`` or ``centos`` and ``$runtime`` with either ``docker``
or ``podman``.

Supported distributions/tags
----------------------------

- ``fedora``: based on ``registry.fedoraproject.org/fedora:latest``
- ``tumbleweed``: based on ``registry.opensuse.org/opensuse/tumbleweed:latest``
- ``centos``: based on ``quay.io/centos/centos:stream9``
- ``leap-15.5``: based on ``registry.opensuse.org/opensuse/leap:15.5``
- ``leap-15.6``: based on ``registry.opensuse.org/opensuse/leap:15.6``


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

  local lspconfig = require("lspconfig")
  local util = require("lspconfig.util")
  local configs = require("lspconfig.configs")
  configs.rpmspec = {
      default_config = {
        cmd = { 'python3', '-mrpm_spec_language_server', '--stdio' },
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

  lspconfig["rpmspec"].setup({})

Neovim with `coc.nvim`_ plugin
------------------------------

.. warning::
   `coc.nvim`_ is licensed under the non-free "activist" `Anti 996 License`_

Open nvim, run ``:CocConfig``\, and merge the following JSON into your
configuration

.. code-block:: json

    {
        "languageserver": {
            "spec": {
                "command": "rpm_lsp_server",
                "args": ["--stdio"],
                "filetypes": ["spec"]
            }
        }
    }


Emacs with `lsp-mode.el`_
-------------------------

``lsp-mode`` has builtin support for the rpm-spec-language-server. All you have
to do is to require ``'lsp-rpm-spec`` and launching ``lsp-mode``. With
``use-package``, this can be implemented as follows utilizing ``rpm-spec-mode``:

.. code-block:: lisp

   (use-package lsp-mode
     :ensure t
     :commands (lsp lsp-deferred)
     :hook ((rpm-spec-mode . lsp-deferred)))

   (use-package rpm-spec-mode
     :ensure t
     :mode "\\.spec'"
     :config (require 'lsp-rpm-spec))


Emacs with `eglot.el`
---------------------

``eglot`` is the builtin LSP Client for Emacs. Support for the
rpm-spec-language-server can be added by evaluating the following snippet
(e.g. in your ``init.el`` or directly in the scratch buffer):

.. code-block:: lisp

   (require 'eglot)
   (add-to-list 'eglot-server-programs
                  '(rpm-spec-mode . ("localhost" 2087)))


Then start the language server in tcp mode and invoke eglot via ``M-x eglot``.

.. _coc.nvim: https://github.com/neoclide/coc.nvim

.. _Anti 996 License: https://github.com/neoclide/coc.nvim/blob/master/LICENSE.md

.. _lsp-mode.el: https://emacs-lsp.github.io/lsp-mode/
