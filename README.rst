RPM SPEC language server
========================

Server supporting LSP protocol for editing RPM Spec files.

The initial effort should be focused mainly on keyword completion and
some kind of linting.

Dependencies
============

- `pygls`_ for easy LSP development
- `lsprotocol`_ which pygls depends on for protocol types
- `thefuzz`_ to easily implement ranked fuzzy keyword
  matches. Might be worth changing later if performance is an
  issue.

Files
=====

/resources
----------

Some reference files that will be useful.

spec.md
~~~~~~~

A copy of
https://github.com/rpm-software-management/rpm/blob/master/docs/man/rpmspec.8.md
which is being used to populate the documentation for preamble keywords
and scriptlets in autocomplete_data.py. We could autofetch this but
there’s zero guarantee it’ll be compatible with the processing script.

/scripts
--------

Processing scripts

extract_docs.py
~~~~~~~~~~~~~~~

Extract information from spec.md and convert it into an
``autocomplete_data.json`` which contains tuples of keywords to complete
and their relevant documentation.

.. _`pygls`:
   https://pypi.org/project/pygls
   
.. _`lsprotocol`:
   https://pypi.org/project/lsprotocol

.. _`thefuzz`:
   https://pypi.org/project/thefuzz
