RPM Spec File Language Server
=============================

Requirements
------------

- Python >= 3.11
- `poetry <https://python-poetry.org/>`_


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
