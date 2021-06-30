batch-calculator
==========================================

Introduction
------------
This tool can be used for reeksberekeningen.

Installation
------------
The easiest way to install the tool is through cloning the repository.

We can also be installed with::

  $ pip install batch-calculator
  
For installation on the utr-con-task-01.nens.local use this (you need administrator rights for this!):

1. First copy this repository to your workdir on your local machine, so that you can access it on the linux-machine

2. Then copy the batch-calculator to the root directory of the linux-machine:
  $ sudo su
  
  $ rm /root/batch-calculator
 
  $ cp /mnt/workdir/A_vtVeld/batch-calculator /root/ -r
  
3. Then install or upgrade the batch-calculator through a local installation procedure:
  $ pip3 install -e /root/batch-calculator --upgrade
  

  
  
Usage
-----

To ensure the correct behaviour of this tool please go through the following steps:

#. Create a folder with all the rain files you want to use in your simulations. These rain files should be in 'min,mm'-format, where min is the timestep in minutes and mm is the amount of rain that falls during the timestep in millimeters. Each timestep is seperated by a newline like in the example below::

    0,5.0
    30,1.5
    60,0.0
#. Create an output folder in which the result files will be stored.
#. If you want to add dry weather flow, download the model sqlite and save it in your project folder.
#. Find the "id" of your model in the Threedi Model List: https://api.3di.live/v3.0/threedimodels/
#. Open a command window and navigate to the batch-calculator folder.
#. Run ``$ python scripts.py -h`` or ``$ run-batch-calculator -h`` to see which arguments you need to specify for your specific case.


Example
-------
Example command::

  $ run-batch-calculator model_id=12345 rain_files_dir=C:\rain_files results_dir=C:\results sqlite_path=C:\model.sqlite --ini_2d_water_level_constant 0.8