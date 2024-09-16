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

Doorloop de volgende stappen om ervoor te zorgen dat deze tool correct werkt:

#. Controleer de schematisatie en simulatie-instellingen (zie "Aandachtspunten 3Di model")
#. Maak een map met alle neerslagbestanden die je in je simulaties wilt gebruiken. Deze regenbestanden moeten het 'min,mm'-formaat hebben, waarbij min de tijdstap in minuten is en mm de hoeveelheid regen die tijdens de tijdstap valt, in millimeters. Elke tijdstap wordt gescheiden door een nieuwe regel, zoals in het onderstaande voorbeeld::

    0,5,0
    30,1,5
    60,0,0
#. Maak een uitvoermap waarin de resultaatbestanden worden opgeslagen.
#. Zoek de ID van uw 3Di-model op 3Di Management
#. Voer op de opdrachtregel ``run-rain-series-simulation --help`` uit om te zien welke argumenten u moet opgeven.
#. Voer op de opdrachtregel ``process-rain-series-results --help`` uit om te zien welke argumenten u moet opgeven.

Voorbeeld
-------

De voorbeelden hieronder laten zien hoe ``threedi-urban-eia-nl`` kan worden gebruikt als command line tool.

  $ run-rain-series-simulations <3Di Model ID> <pad\naar\neerslagbestandenmap> <pad\naar\resultatenmap> -o <organisatie UUID (optioneell)> -h <host (optional)>

  $ process-rain-series-results <created simulations json file> -h <host (optional)> -d <sets debug flag to True> -s <skips downloading result files>

Voorbeeldcommando's::

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

Aangemaakte bestanden en mappen
-------------------------------

- aggregation_netcdf, map met geaggregeerde resultaten van de simulatie
- simulations, map met simulatieloggegevens (gebruik de optie --debug)
- threedi_urban_eia_nl_statistics.csv, batchberekeningsresultaat. Het bevat de volgende kolommen:
    - weir_id
    - frequency: hoe vaak gemiddeld per jaar een overstort plaats vindt (totaal aantal overstortingen/10 of 25 jaar. Afhankelijk of de reeks over 10 of over 25 jaar is berekend)
    - average_volume: het gemiddelde overstort volume per jaar (totaal overstort volume/10 jaar of 25 jaar )
    - T=1, T=2, T=5 en T=10: volume wat je kan verwachten per herhalingstijd
- crashed_simulations.json, ID's van gecrashte simulaties (optioneel)
- create_simulations_<datum>.json, informatie over uitgevoerde simulaties, dient als invoerbestand voor ``proces-rain-series-results``
- gridadmin.h5, noodzakelijk voor berekening van batchstatistieken
- nan_rows.json, informatie over stuwen die NaN-gegevens bevatten in hun cumulatieve afvoer (optioneel)
