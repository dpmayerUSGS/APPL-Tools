#!/usr/bin/env python3
import sys
import argparse
import requests
import json
import re
from osgeo import gdal,ogr,osr

def parse_args(print_usage=False):
    ## Create argument parser
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description = """Download LOLA, MLA, or MOLA shot data within a geographic region using the PDS Geoscience Node's Orbital Data Explorer REST interface. 
The search region may be defined by explicitly listing bounding latitudes and longitudes or by passing a map-projected raster as input.
The script will parse the server's response and download the 'pts_csv' flavor of CSV product and accompanying PDS3 label.
LOLA and MOLA queries may be submitted synchronously or asynchronously but MLA queries *must* be submitted asynchronously.

See the ODE REST Manual for detailed information on which fields are contained in the output files for each product type:
https://oderest.rsl.wustl.edu/""",
                                 epilog = """EXAMPLES:
  Search for LOLA shots based on bounding coordinates
      %(prog)s moon --coords 44.0 44.1 340.5 340.6 \n

  Search for MOLA shots by passing a GeoTIFF and let the script calculate the lat/lon bounds of the image
      %(prog)s mars --raster my_projected_image.tif \n

  Search for MLA shots asynchronously and request an email when the job is finished
      %(prog)s mercury --async --email name@example.com --raster mercury_image.tif \n

  An asynchronous query will generate a numeric Job ID. This Job ID can be passed to %(prog)s to determine the status of the job.
  If the job has finished, the script will automatically download the pts_csv CSV and accompanying PDS3 label.
   %(prog)s --status 55117

KNOWN ISSUES:
Passing in images with a polar stereographic projection or that straddle one of the poles will yield undesirable results. 
Users should instead manually specify bounding coordinates for areas over the poles.\n

The script has no way of determining if the target specified on the command line matches the target of a given raster. 
Users must take care to pass input images that correspond to the desired output product.

""")

    parser.add_argument("target",
                        choices = ["mars","mercury","moon"],
                        type = str.lower,
                        nargs='?',
                        help = """Name of target body. "Mars," "Mercury," and "Moon" return data from MOLA, MLA, and LOLA, respectively. """)
    parser.add_argument("--async",
                            action='store_true',
                            dest="async_",
                            help = """Submit query in asynchronous mode. Required when target is Mercury.""")
    parser.add_argument("--email",
                            nargs=1,
                            type=str.lower,
                            metavar = "name@example.com",
                            help="Send email to this address when the job finishes. Recommended for asynchronous jobs.")    
    parser.add_argument('--status',
                        nargs=1,
                        type = int,
                        metavar = "JobID",
                        help = "Get status of a previously-submitted job with given job ID and download data if job is complete. If passed, any other commandline arguments are ignored.")

    # In Target Mode, there are 2 mutually exclusive options: coords and raster, each with their own required args
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--coords",
                       nargs=4,
                       type=float,
                       metavar=('minlat', 'maxlat', 'westernlon', 'easternlon'))
    group.add_argument("--raster",
                       nargs=1,
                       metavar="file")
    

    args = parser.parse_args()
    if print_usage:
        parser.print_usage()
    else:
        return args

def isValidEmail(email):
    """
    Test if a given string resembles an email address


    Parameters
    ----------
    email   : str

    Returns
    -------
    result :  boolean

    """
    
    if len(email) > 4:
        if re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email) != None:
            return True

def ValidateCoords(coords):
    """
    Check that latitude/longitude values defining a bounding box are within acceptable ranges


    Parameters
    ----------
    coords   : list
               List of coordinates to evaluate: minlat, maxlat, minlon, maxlon

    Returns
    -------
    result :  boolean

    """
    
    result = True
    if coords[0] < -90 or coords[0] >= 90:
        print("Error: minlat must be >= -90 and < 90")
        result = False
    if coords[1] <= -90 or coords[1] > 90:
        print("Error: maxlat must be > -90 and <= 90")
        result = False
    if coords[2] < -180 or coords[2] >= 360:
        print("westernlon must be >= -180 and < 360")
        result = False
    if coords[3] <= -180 or coords[3] > 360:
        print("easternlon must be > -180 and <= 360")
        result = False
    # Check that coords are internally consistent
    if coords[0] >= coords[1]:
        print("minlat must be < maxlat")
        result = False
    if coords[2] >= coords[3]:
        print("westernlon must be < easternlon")
        result = False
    return result

def LonTo360(dlon):
    # Convert longitudes to 0-360 deg
    dlon = ((360 + (dlon % 360)) % 360)
    return dlon

# https://gis.stackexchange.com/questions/57834/how-to-get-raster-corner-coordinates-using-python-gdal-bindings
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

def get_raster_extent(raster):
    """
    Get minimum bounding rectangle (MBR) of a given raster, expressed in latitude and longitude


    Parameters
    ----------
    raster :  str
              Path to a map-projected raster

    Returns
    -------
    coords   : list
               List of bounding coordinates: [minlat, maxlat, minlon, maxlon]

    """
    ds = gdal.Open(raster)
    gt = ds.GetGeoTransform()
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    ext = []
    xarr = [0,cols]
    yarr = [0,rows]

    for px in xarr:
        for py in yarr:
            x = gt[0]+(px*gt[1])+(py*gt[2])
            y = gt[3]+(px*gt[4])+(py*gt[5])
            ext.append([x,y])
        yarr.reverse()

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

    return coords

def download_pts(gdsResultFiles):
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
    return

def main(user_args):
    print(user_args)

    gdal.UseExceptions()

    # Check for sane commandline arguments
    # Check for --status first, ignore any other arguments that may have been passed
    if user_args.status:
        target = None
        jobid = user_args.status[0]  
    elif user_args.target:
        target = user_args.target
        async_ = user_args.async_
        email = user_args.email
        # Require one of --raster or --coords if body is specified
        if user_args.raster:
            coords = get_raster_extent(user_args.raster[0])
        elif user_args.coords:
            coords = user_args.coords
        else:
            print("Must specify either raster or bounding coordinates when passing a target body.", file=sys.stderr)
            parse_args(print_usage=True)
            sys.exit(1)
    else:
        # print usage and exit
        parse_args(print_usage=True)
        sys.exit(0)

    # Build payload
    if target:
        # Force use of --async when target is Mercury
        # (There isn't an easy way to enforce this with argparse because async is otherwise optional)
        if target == "mercury" and async_ is False:
            print("ERROR: Must use --async flag when target is Mercury", file=sys.stderr)
            sys.exit(1)

        # Dict to associate target passed on command line with product type the ODE REST interface is expecting
        products = {'mars': 'molapedr',
                    'mercury': 'mlardr',
                    'moon': 'lolardr'}

        if ValidateCoords(coords):
            for i in [2,3]:
                coords[i] = LonTo360(coords[i])
                
        else:
            print("Invalid coordinates", file=sys.stderr)
            sys.exit(1)

        payload = {'results': 'v',
                   'output': 'json',
                   'query': products[target],
                   'minlat': coords[0],
                   'maxlat': coords[1],
                   'westernlon': coords[2],
                   'easternlon': coords[3] }

        if email:
            # if email, it will be a single item list
            email = email[0]
            if not isValidEmail(email):
                print("Error: " + email + "does not appear to be a valid email address", file=sys.stderr)
                sys.exit(1)
            else:
                payload['email'] = email

        if async_:
            payload['async'] = "t"
        else:
            payload['async'] = "f"
    elif jobid:
        print("Checking status of JobID " + str(jobid))
        payload = {'jobid': jobid,
                   'output': 'json'}

    # At this point, regardless of which mode was invoked, we should have a payload for the ODE REST query
    print("Submitting query. Please wait...")
    try:
        r = requests.get('http://oderest.rsl.wustl.edu/livegds', params=payload)
        print(r.url)
        gdsResults = r.json()
    except requests.exceptions.RequestException as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    # Get status code from response
    gdsStatus = (gdsResults['GDSResults']['Status']).upper()

    # Manage the query response depending on which mode was invoked
    print("Results:")
    if target:
        if gdsStatus == "SUCCESS":
            if async_:
                jobid = gdsResults['GDSResults']['JobId']
                print("   Status:  " + gdsStatus)
                print("   JobID:   " + jobid )
                print("Check job status at: ")
                print("http://oderest.rsl.wustl.edu/livegds/?jobid=" + jobid + "&output=json")
                print("or by running ")
                print("        ode_get_laser_alt.py status " +jobid)
                if email:
                    print("A message will be sent to " + email + " when the job finishes.")
            else:
                gdsStatusNote = gdsResults['GDSResults']['StateSummary']['StatusNote']
                gdsCount = gdsResults['GDSResults']['Count']
                gdsResultFiles = gdsResults['GDSResults']['ResultFiles']['ResultFile']

                print("   Status:  " + gdsStatus)
                print("   Count:   " + gdsCount)
                print("   StatusNote:  "+ gdsStatusNote)
                download_pts(gdsResultFiles)
        elif gdsStatus == "ERROR":
            gdsError = gdsResults['GDSResults']['Error']
            print("   Status:  "+ gdsStatus)
            print("   Error:  "+ gdsError)
        else:
            print("Unexpected response received from ODE REST Service")
            print(json.dumps(gdsResults, indent=4, sort_keys=True))

    elif jobid:
        if gdsStatus == 'SUCCESS':
            gdsState = (gdsResults['GDSResults']['StateSummary']['State']).upper()
            if gdsState == "FINISHED":
                gdsStatusNote = gdsResults['GDSResults']['StateSummary']['StatusNote']
                gdsCount = gdsResults['GDSResults']['Count']
                gdsResultFiles = gdsResults['GDSResults']['ResultFiles']['ResultFile']
                print("   Status:  " + gdsStatus)
                print("   Count:   " + gdsCount)
                print("   StatusNote:  "+ gdsStatusNote)
                download_pts(gdsResultFiles)
            elif gdsState == ( "RUNNING" or "WAITING" or "ERROR" or "UNKNOWN" ):
                gdsStatusNote = gdsResults['GDSResults']['StateSummary']['StatusNote']
                print("   Status:  " + gdsState)
                print("   StatusNote:  "+ gdsStatusNote)
            else:
                print("Unexpected State response received from ODE REST Service")
                print(json.dumps(gdsResults, indent=4, sort_keys=True))
        elif gdsStatus == "ERROR":
            gdsError = gdsResults['GDSResults']['Error']
            print("   Status:  "+ gdsStatus)
            print("   Error:  "+ gdsError)
        else:
            print("Unexpected response received from ODE REST Service")
            print(json.dumps(gdsResults, indent=4, sort_keys=True))

if __name__ == "__main__":
    sys.exit(main(parse_args()))
