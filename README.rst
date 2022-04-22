batch-calculator
==========================================

Introduction
------------
This tool can be used for reeksberekeningen.

Installation
------------
The easiest way to install the tool is through cloning the repository.

For installation on the utr-con-task-01.nens.local use this (you need administrator rights for this!):

1. First copy this repository to your workdir on your local machine, so that you can access it on the linux-machine

2. Then copy the batch-calculator to the root directory of the linux-machine::

    $ sudo su
    $ rm -r /root/batch-calculator
    $ cp /mnt/workdir/A_vtVeld/batch-calculator /root/ -r

3. Then install or upgrade the batch-calculator through a local installation procedure::

    $ pip3 install -e /root/batch-calculator --upgrade

Usage
-----

To ensure the correct behaviour of this tool please go through the following steps:

#. Create a folder with all the rain files you want to use in your simulations. These rain files should be in 'min,mm'-format, where min is the timestep in minutes and mm is the amount of rain that falls during the timestep in millimeters. Each timestep is seperated by a newline like in the example below::

    0,5.0
    30,1.5
    60,0.0
#. Create an output folder in which the result files will be stored.
#. Find the "id" of your model in the Threedi Model List: https://api.3di.live/v3/threedimodels/
#. Open a command window and navigate to the batch-calculator folder.
#. Run ``$ run-rain-series-simulations --help`` to see which arguments you need to specify.
#. Run ``$ process-rain-series-results --help`` to see which arguments you need to specify.

Example
-------

  $ run-rain-series-simulations <ThreediModel ID> <rain files dir> <results dir> <username> -o <organisation (optional)> -h <host (optional)>

  $ process-rain-series-results <created simulations json file> <username> -h <host (optional)>

Example command::

  $ run-rain-series-simulations 12345 rain_files/ results/ daan.vaningen

  $ process-rain-series-results results/created_simulations.json daan.vaningen