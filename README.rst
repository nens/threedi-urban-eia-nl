batch-calculator
==========================================

Introduction

Usage, etc.


Installation
------------

We can be installed with::

  $ pip install batch-calculator

(TODO: after the first release has been made)


Development installation of this project itself
-----------------------------------------------

We use python's build-in "virtualenv" to get a nice isolated directory. You
only need to run this once::

  $ python3 -m venv .

A virtualenv puts its commands in the ``bin`` directory. So ``bin/pip``,
``bin/pytest``, etc. Set up the dependencies like this::

  $ bin/pip3 install -r requirements.txt

There will be a script you can run like this::

  $ bin/run-batch-calculator

It runs the `main()` function in `batch-calculator/scripts.py`,
adjust that if necessary. The script is configured in `setup.py` (see
`entry_points`).

In order to get nicely formatted python files without having to spend manual
work on it, run the following command periodically::

  $ bin/black batch_calculator

Run the tests regularly. This also checks with pyflakes, black and it reports
coverage. Pure luxury::

  $ bin/pytest

The tests are also run automatically `on travis-ci
<https://travis-ci.com/nens/batch-calculator>`_, you'll see it
in the pull requests. There's also `coverage reporting
<https://coveralls.io/github/nens/batch-calculator>`_ on
coveralls.io (once it has been set up).

If you need a new dependency (like `requests`), add it in `setup.py` in
`install_requires`. Afterwards, run pip again to actually install your
dependency::

  $ bin/pip3 install -r requirements.txt


Steps to do after generating with cookiecutter
----------------------------------------------

- Update this readme. Use `.rst
  <http://www.sphinx-doc.org/en/stable/rest.html>`_ as the format.

- Remove this section as you've done it all :-)
