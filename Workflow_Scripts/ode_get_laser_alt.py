#!/usr/bin/env python3

#/******************************************************************************
# * $Id$
# *
# * Name:     ode_get_laser_alt.py
# * Purpose:  Download LOLA or MOLA shot data within a geographic region using
# *            the PDS Geoscience Node's Orbital Data Explorer REST interface.
# *
# * Author:   David P. Mayer, dpmayer@usgs.gov
# *
# * License:  Public Domain
# *
# ******************************************************************************

import argparse
from osgeo import gdal,osr  # 3rd party library
import requests             # 3rd party library
import sys

gdal.UseExceptions()

def parse_arguments():
    ## Create argument parser
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description = """Download LOLA or MOLA shot data within a geographic region using the PDS Geoscience Node's Orbital Data Explorer REST interface. 
The search region may be defined by explicitly listing bounding latitudes and longitudes or by passing a map-projected raster as input.
The script will parse the server's response and download the 'pts_csv' flavor of CSV product and accompanying PDS3 label.

See the ODE REST Manual for detailed information on which fields are contained in the output files for each product type:
http://oderest.rsl.wustl.edu/""",
                                 epilog = """EXAMPLES:
  Search for LOLA shots based on bounding coordinates
      %(prog)s moon --coords 44.0 44.1 340.5 340.6 \n

  Search for MOLA shots by passing a GeoTIFF and let the script calculate the lat/lon bounds of the image
      %(prog)s mars --raster my_projected_image.tif

KNOWN ISSUES:
Passing in images with a polar stereographic projection or that straddle one of the poles will yield undesirable results. 
Users should instead manually specificy bounding coordinates for areas over the poles.\n

The script has no way of determining if a raster passed as input contains data from the same target body 
specified on the command line. Thus, one could pass in an image of Mars as input but specify "Moon" as the target, 
and the script will return LOLA data within the latitude and longitude bounds that define the Mars image. 
Users must take care to pass input images that correspond to the desired output product.

""")

    parser.add_argument('target',
                    choices = ["mars","moon"],
                    type = str.lower, # effectively make this case insensitive
                    help = """Name of target body. "Mars" will return MOLA data and "Moon" will return LOLA data. """)

    ## User must specify exactly one of --coords or --raster
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--coords',
                   nargs = 4,
                   type = float,
                   metavar = ('minlat', 'maxlat', 'westernlon', 'easternlon'),
                   help = """Manually list the bounding coordinates for the query. 
                           Latitudes may range from -90 to 90 degrees. 
                           Longitudes may range from -180 to 360 degrees, positive east.""")
    group.add_argument('--raster',
                   nargs = 1,
                   metavar = "file",
                   help = """Pass a raster named 'file' that contains GDAL-compatible projection information, 
                           such as a GeoTIFF or Level 2 ISIS3 cube.""")

    ## Parse the command line arguments
    args = parser.parse_args()
    return args

def ValidateCoords(coords):
    # Check that coords are within acceptable ranges
    ## Validate the specific lat/lon bounds
    ## This isn't strictly necessary because the server will validate the input params,
    ##  but doing it before sending a query saves time.
    if coords[0] < -90 or coords[0] >= 90:
        print("Error: minlat must be >= -90 and < 90")
        sys.exit(1)
    if coords[1] <= -90 or coords[1] > 90:
        print("Error: maxlat must be > -90 and <= 90")
        sys.exit(1)
    if coords[2] < -180 or coords[2] >= 360:
        print("westernlon must be >= -180 and < 360")
        sys.exit(1)
    if coords[3] <= -180 or coords[3] > 360:
        print("easternlon must be > -180 and <= 360")
        sys.exit(1)

    # Check that coords are internally consistent
    if coords[0] >= coords[1]:
        print("minlat must be < maxlat")
        sys.exit(1)
    if coords[2] >= coords[3]:
        print("westernlon must be < easternlon")
        sys.exit(1)

def LonTo360(coords):
    # Convert longitudes to 0-360 deg
    coords[2] = ((360 + coords[2]) % 360)
    coords[3] = ((360 + coords[3]) % 360)
    # Return updated coords
    return coords

## Functions GetExtent() and ReprojectCoords() copied from
##  https://gis.stackexchange.com/questions/57834/how-to-get-raster-corner-coordinates-using-python-gdal-bindings
def GetExtent(gt,cols,rows):
    ''' Return list of corner coordinates from a geotransform

        @type gt:   C{tuple/list}
        @param gt: geotransform
        @type cols:   C{int}
        @param cols: number of columns in the dataset
        @type rows:   C{int}
        @param rows: number of rows in the dataset
        @rtype:    C{[float,...,float]}
        @return:   coordinates of each corner
    '''
    ext = []
    xarr = [0,cols]
    yarr = [0,rows]

    for px in xarr:
        for py in yarr:
            x = gt[0]+(px*gt[1])+(py*gt[2])
            y = gt[3]+(px*gt[4])+(py*gt[5])
            ext.append([x,y])
        yarr.reverse()
    return ext

def ReprojectCoords(coords,src_srs,tgt_srs):
    ''' Reproject a list of x,y coordinates.

        @type geom:     C{tuple/list}
        @param geom:    List of [[x,y],...[x,y]] coordinates
        @type src_srs:  C{osr.SpatialReference}
        @param src_srs: OSR SpatialReference object
        @type tgt_srs:  C{osr.SpatialReference}
        @param tgt_srs: OSR SpatialReference object
        @rtype:         C{tuple/list}
        @return:        List of transformed [[x,y],...[x,y]] coordinates
    '''
    trans_coords = []
    transform = osr.CoordinateTransformation( src_srs, tgt_srs)
    for x,y in coords:
        x,y,z = transform.TransformPoint(x,y)
        trans_coords.append([x,y])
    return trans_coords



command_line_args = parse_arguments()
## Dict to associate target passed on command line with product type the ODE REST interface is expecting
products = {'mars': 'molapedr',
            'moon': 'lolardr'}

if command_line_args.coords is not None:
    coords = command_line_args.coords
    ValidateCoords(coords)
    LonTo360(coords)
    print(coords)
elif command_line_args.raster is not None:
    try:
        raster = command_line_args.raster[0]
        ds = gdal.Open(raster)
        gt = ds.GetGeoTransform()
        cols = ds.RasterXSize
        rows = ds.RasterYSize
        ext = GetExtent(gt,cols,rows)

        src_srs = osr.SpatialReference()
        src_srs.ImportFromWkt(ds.GetProjection())
        if not ds.GetProjection():
            print("Error: " + raster + " does not appear to have an associated map projection")
            sys.exit(1)
        
        # Define the target SRS as the geographic coord sys of the source SRS
        # This causes ReprojectCoords() to return lat/lon values
        tgt_srs = src_srs.CloneGeogCS()

        geo_ext = ReprojectCoords(ext,src_srs,tgt_srs)
        coords = []
        coords.append(min(geo_ext[1][1],geo_ext[2][1]))
        coords.append(max(geo_ext[0][1],geo_ext[3][1]))
        coords.append(min(geo_ext[0][0],geo_ext[1][0]))
        coords.append(max(geo_ext[2][0],geo_ext[3][0]))
        
        ValidateCoords(coords)
        LonTo360(coords)

    except RuntimeError as e:
        print(e)
        sys.exit(1)

## Careful use of argparse should preclude ever falling through to this point
##  but an "else" is included here, just in case
else:
    print("Must specify either --coords or --raster on commandline")
    sys.exit(1)


payload = {'results': 'v',
           'output': 'json',
           'query': products[command_line_args.product] ,
           'minlat': coords[0] ,
           'maxlat': coords[1] ,
           'westernlon': coords[2] ,
           'easternlon': coords[3] }

print("Submitting query. Please wait...")
r = requests.get('http://oderest.rsl.wustl.edu/livegds', params=payload)
print(r.url)
gdsResults = r.json()

## Report the status returned by ODE and act accordingly
gdsStatus = gdsResults['GDSResults']['Status']
print(gdsStatus)
if gdsStatus == "Success":
    gdsStatusNote = gdsResults['GDSResults']['StateSummary']['StatusNote']
    gdsResultFiles = gdsResults['GDSResults']['ResultFiles']['ResultFile']

    print("Results:")
    print("   Status:  "+ gdsStatus)
    print("   StatusNote:  "+ gdsStatusNote)

    for i in gdsResultFiles:
        # Only download the "pts_csv" flavor of CSV.
        # See ODE's GDS REST manual for description
        if 'pts_csv' in i['URL']:
            fileurl = i['URL']
            filename = fileurl.split('/')[-1]
            print("Downloading " + fileurl)
            r = requests.get(fileurl, stream=True)
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

elif gdsStatus == "Error":
    gdsError = gdsResults['GDSResults']['Error']
    print("Results:")
    print("   Status:  "+ gdsStatus)
    print("   Error:  "+ gdsError)
    
else:
    print("Unexpected response received from ODE")
    print(gdsResults)
