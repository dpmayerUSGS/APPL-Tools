# workflow scripts
Collection of Python workflow script written for SocetGXP

Scripts:
  ode_get_laser_alt.py
  ode_csv2shapefile.py



--------------------------------------------------------------------------------
usage: ode_get_laser_alt.py [-h]
                            (--coords minlat maxlat westernlon easternlon | --raster file)
                            {mars,moon}

Download LOLA or MOLA shot data within a geographic region using the PDS Geoscience Node's Orbital Data Explorer REST interface. 
The search region may be defined by explicitly listing bounding latitudes and longitudes or by passing a map-projected raster as input.
The script will parse the server's response and download the 'pts_csv' flavor of CSV product and accompanying PDS3 label.

See the ODE REST Manual for detailed information on which fields are contained in the output files for each product type:
http://oderest.rsl.wustl.edu/

positional arguments:
  {mars,moon}           Name of target body. "Mars" will return MOLA data and
                        "Moon" will return LOLA data.

optional arguments:
  -h, --help            show this help message and exit
  --coords minlat maxlat westernlon easternlon
                        Manually list the bounding coordinates for the query.
                        Latitudes may range from -90 to 90 degrees. Longitudes
                        may range from -180 to 360 degrees, positive east.
  --raster file         Pass a raster named 'file' that contains GDAL-
                        compatible projection information, such as a GeoTIFF
                        or Level 2 ISIS3 cube.

EXAMPLES:
  Search for LOLA shots based on bounding coordinates
      ode_get_laser_alt.py moon --coords 44.0 44.1 340.5 340.6 

  Search for MOLA shots by passing a GeoTIFF and let the script calculate the lat/lon bounds of the image
      ode_get_laser_alt.py mars --raster my_projected_image.tif

KNOWN ISSUES:
Passing in images with a polar stereographic projection or that straddle one of the poles will yield undesirable results. 
Users should instead manually specificy bounding coordinates for areas over the poles.

The script has no way of determining if a raster passed as input contains data from the same target body 
specified on the command line. Thus, one could pass in an image of Mars as input but specify "Moon" as the target, 
and the script will return LOLA data within the latitude and longitude bounds that define the Mars image. 
Users must take care to pass input images that correspond to the desired output product.







--------------------------------------------------------------------------------

usage: ode_csv2shapefile.py [-h]
                            [--input file.csv | --pattern "*_pts_csv.csv"]
                            {mars,moon,mercury}

Convert ODE created LOLA, MOLA, or MLA shot data to an Esri pointZ Shapefile.
The CSV is expected to be generated from the script ode_get_laser_alt.py

positional arguments:
  {mars,moon,mercury}   Specify which target: Mars, Moon, Mercury

optional arguments:
  -h, --help            show this help message and exit
  --input file.csv      an input ODE csv file as downloaded using
                        ode_get_laser_alt.py.
  --pattern "*_pts_csv.csv"
                        pattern to find and run on many strings. Default
                        pattern is "*_pts_csv.csv".

EXAMPLES:
         ode_csv2shapefile.py Mars --input ode_lolardr.csv 
         ode_csv2shapefile.py Moon --input ode_molapedr.csv
         ode_csv2shapefile.py Moon --pattern "*_pts_csv.csv"