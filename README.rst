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

We're installed with `pipenv <https://docs.pipenv.org/>`_, a handy wrapper
around pip and virtualenv. Install that first with ``pip install
pipenv``. Then run::

  $ PIPENV_VENV_IN_PROJECT=1 pipenv --three
  $ pipenv install --dev

There will be a script you can run like this::

  $ pipenv run run-batch-calculator

It runs the `main()` function in `batch-calculator/scripts.py`,
adjust that if necessary. The script is configured in `setup.py` (see
`entry_points`).

In order to get nicely formatted python files without having to spend manual
work on it, run the following command periodically::

  $ pipenv run black batch_calculator

Run the tests regularly. This also checks with pyflakes, black and it reports
coverage. Pure luxury::

  $ pipenv run pytest

The tests are also run automatically `on travis-ci
<https://travis-ci.com/nens/batch-calculator>`_, you'll see it
in the pull requests. There's also `coverage reporting
<https://coveralls.io/github/nens/batch-calculator>`_ on
coveralls.io (once it has been set up).

If you need a new dependency (like `requests`), add it in `setup.py` in
`install_requires`. Afterwards, run install again to actuall install your
dependency::

  $ pipenv install --dev


Steps to do after generating with cookiecutter
----------------------------------------------

- Add a new project on https://github.com/nens/ with the same name. Set
  visibility to "public" and do not generate a license or readme.

  Note: "public" means "don't put customer data or sample data with real
  persons' addresses on github"!

- Follow the steps you then see (from "git init" to "git push origin master")
  and your code will be online.

- Go to
  https://github.com/nens/batch-calculator/settings/collaboration
  and add the teams with write access (you might have to ask someone with
  admin rights to do it).

- Update this readme. Use `.rst
  <http://www.sphinx-doc.org/en/stable/rest.html>`_ as the format.

- Ask Reinout to configure travis and coveralls.

- Remove this section as you've done it all :-)
