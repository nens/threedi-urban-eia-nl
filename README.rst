batch-calculator
==========================================

Introduction


Installation
------------
Clone the repository

We can also be installed with::

  $ pip install batch-calculator
  
  
Usage
-----

To ensure the correct behaviour of this tool please go through the following steps:

#. Fill in your API/3Di username and password in the premade .env file located in the batch-calculator directory.
#. Create a folder with all the rain files you want to use in your simulations. These rain files should be in 'min,mm'-format, where min is the timestep in minutes and mm is the amount of rain that falls during the timestep in millimeters.
#. Create an output folder in which the result files will be stored.
#. Open a command window and navigate to the batch-calculator folder.
#. Run $ python scripts.py -h to see which arguments you need to specify for your specific case.



