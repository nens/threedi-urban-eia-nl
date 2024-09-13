threedi-urban-eia-nl
====================

Note for non-Dutch speakers
---------------------------

This package is intended for environmental impact analysis of sewerage systems in the Netherlands. It follows the standard procedures that are prescribed for such analyses in the Netherlands. As such, it is not useful for applications outside of the Netherlands. For this reason, the rest of the documentation is in Dutch.

Inleiding
---------
Voor de analyse van het milieutechnisch functioneren zoals beschreven in de Kennisbank Stedelijk Water van Stichting Rioned wordt een standaardreeks buien doorgerekend. Met ``threedi-urban-eia-nl`` kan je via de command line of met Python deze neerslagreeks met 3Di door te rekenen. Met behulp van een reeksberekening bepaal je het milieutechnisch functioneren van overstorten. Bij de milieutechnische toetsing ligt de focus op de vuilemissies en overstortfrequenties van overstorten. De doorgerekende reeks is doorgaans een selectie van buien over de periode van 1955 - 1964. Voor meer achtergrondinformatie zie: https://www.riool.net/standaardneerslagreeks

Aandachtspunten 3Di-model
-------------------------

Let op de volgende zaken:

* De pompen van bergbezinkvoorzieningen zijn ook geschematiseerd.

* De DWA-belasting varieert over de tijd volgens het standaardverloop.

* Van de externe overstorten (ook van de bergbezinkvoorzieningen) worden de volgende resultaten verwacht (let op bij dubbele kunstwerken).

  * Overstortfrequentie [per jaar]
  * Gemiddeld overstortvolume [m3/jaar]
  * Chemisch zuurstof verbruik (CZV) [kg CZV/jaar]
  * Externe overstort: CZV = Gemiddeld overstortvolume * 0.25
  * Bergbezinkvoorziening (externe overstort): CZV = Gemiddeld overstortvolume * 0.25 * 0.55
  
De berekening van de herhalingstijden wordt hier verder toegelicht: https://www.riool.net/presenteren-van-milieutechnisch-functioneren

Om de statistieken over de simulaties te berekenen moeten de onderstaande aggregation settings zijn gedefinieerd. 

+---------------+--------------------+-----------+
| Flow variable | Aggregation method | Time step |
+---------------+--------------------+-----------+
| discharge     | cum                | 3600      |
+---------------+--------------------+-----------+
| discharge     | cum_positive       | 3600      |
+---------------+--------------------+-----------+
| discharge     | cum_negative       | 3600      |
+---------------+--------------------+-----------+

Dit betreft het cumulatieve volume dat over de overstort gaat, het cumulatieve volume in positieve richting en het cumulatieve volume in negatieve richting.

Hiervoor kan je de volgende SQL gebruiken::

    INSERT INTO aggregation_settings (flow_variable, aggregation_method, time_step)
    VALUES
        ('discharge', 'cum', '3600'),
        ('discharge', 'cum_positive', '3600'),
        ('discharge', 'cum_negative', '3600')
    ;

Zet de output time step ook hoog (bv 3600) omdat je anders erg grote results_3di.nc NetCDFs krijgt.

Installatie
-----------

De eenvoudigste manier om `threedi-urban-eia-nl` te installeren is met ``pip``. Open (met administrator rechten) een command line interface in het python environment waar je in wilt werken, en voer het volgende commando uit:

    ``pip install threedi-urban-eia-nl``

Gebruikershandleiding
---------------------

To ensure the correct behaviour of this tool please go through the following steps:

#. Create a folder with all the rain files you want to use in your simulations. These rain files should be in 'min,mm'-format, where min is the timestep in minutes and mm is the amount of rain that falls during the timestep in millimeters. Each timestep is seperated by a newline like in the example below::

    0,5.0
    30,1.5
    60,0.0
#. Create an output folder in which the result files will be stored.
#. Find the ID of your 3Di model on 3Di Management
#. On the command line, run ``run-rain-series-simulations --help`` to see which arguments you need to specify.
#. On the command line, run ``process-rain-series-results --help`` to see which arguments you need to specify.

Example
-------

  $ run-rain-series-simulations <3Di Model ID> <rain files dir> <results dir> -o <organisation (optional)> -h <host (optional)>

  $ process-rain-series-results <created simulations json file> -h <host (optional)> -d <sets debug flag to True> -s <skips downloading result files>

Example command::

  $ run-rain-series-simulations 12345 rain_files/ results/ user.name

  $ process-rain-series-results results/created_simulations.json user.name

Werking
-------

De reeksberekening bestaat uit twee fases.

Eerste fase:

* Het model wordt 3 dagen droog doorgerekend

* Voor elk uur van dag 3 wordt een ``saved state`` aangemaakt, die worden gebruikt als start van de buien die in fase 2 worden doorgerekend

Tweede fase:

* Voor elke opgegeven bui wordt een simulatie gestart

* De bestandsnaam geeft de start- en eindtijd van de neerslaggebeurtenis weer

Created Files and Directories
-----------------------------

- aggregation_netcdf, directory containing simulation aggregate result data
- simulations, directory containing simulation log data (use --debug option)
- threedi_urban_eia_nl_statistics.csv, batch calculation result
- crashed_simulations.json, IDs of crashed simulations (optional)
- created_simulations_<date>.json, information about created simulations, serves as input file for process-rain-series-results
- gridadmin.h5, necessary for calculation of batch statistics
- nan_rows.json, information about weirs that contain NaN data in their cumulative discharge (optional)

