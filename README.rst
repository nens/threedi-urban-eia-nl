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
#. Run ``$ python scripts.py -h`` to see which arguments you need to specify for your specific case.


Example
-------
Example command::

  $ python scripts.py model_id=12345 rain_files_dir=C:\rain_files results_dir=C:\results sqlite_path=C:\model.sqlite --ini_2d_water_level_constant 0.8