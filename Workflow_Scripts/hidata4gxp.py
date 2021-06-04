#!/usr/bin/env python
import sys
import os
from os import path
import argparse
import subprocess
from pysis import isis
from pysis.exceptions import ProcessError
import pandas as pd
import numpy as np
from osgeo import gdal, ogr, osr
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree

from appl_tools.config import mola_delta_radius_iau, pedr_list
from appl_tools.pedr import pedr2tab_prm, run_pedr2tab, pedrtab2df, pedrcsv2vrt

def parse_args():
    parser = argparse.ArgumentParser(
                                     description="""Naive port of hidata4socet.pl to Python
""")
    parser.add_argument("project_name",
                        help = "Name of the project in Socet Set or Socet GXP.")
    parser.add_argument("noproj_cube",
                        nargs=2,
                        help = """Path to noproj'd cube that belongs to the stereopair. Script accepts exactly 2 cubes.""")
                        
    args = parser.parse_args()
    return args

def dd2dms(dd):
    """
    Convert a decimal to degrees, minutes, seconds.

    Parameters
    ----------
    dd     : numeric
             The decimal to convert

    Returns
    -------
    d,m,s  : list
             List of the integer degrees, integer minutes, and float seconds

    """

    d = int(dd)
    dm = (dd - d)*60
    m = int(dm)
    s = float((dm - m)*60)

    return d,m,s
        
def write_hidata_stats(rlat,rlon,minZ,maxZ,outfile):
    """
    Write the geographic reference point and min/max elevation to a file.
    Formatted for legacy compatibility with Socet Set workflow.


    Parameters
    ----------
    rlat   : list
             List containing degrees, minutes, and seconds of the reference latitude
             Seconds in the list are ignored and set to 00.0 in the output for legacy compatibility

    rlon   : list
             List containing degrees, minutes, and seconds of the reference longitude
             Seconds in the list are ignored and set to 00.0 in the output for legacy compatibility

    minZ   : numeric
             The minimum elevation of the cropped MOLA DEM

    maxZ   : numeric
             The maximum elevation of the cropped MOLA DEM

    outfile  : path
               Path to the file to write output to

    Returns
    -------
    None

    """
    
    s1 = """Geographic reference point: Latitude  = {}:{}:{}\n""".format(str(rlat[0]), str(rlat[1]).zfill(2), str("00.0"))
    s2 = """                            Longitude = {}:{}:{}\n\n""".format(str(rlon[0]), str(rlon[1]).zfill(2), str("00.0"))
    s3 = """Minimum Elevation: {}\n""".format(str(minZ))
    s4 = """Maximum Elevation: {}\n""".format(str(maxZ))
    
    try:
        with open(outfile, 'w') as rpt:
            r = rpt.writelines([s1,s2,s3,s4])
            rpt.close
    except:
        print("Error writing statistics file " + outfile, file=sys.stderr)
    
    return
        
def camrange_mbr(camrange_pvl):
    """
    Parse ISIS camrange results by running ISIS getkey, and return a list of the latitude/longitude extents.
    Planetocentric latitudes, +/-180, positive east longitude domain


    Parameters
    ----------
    camrange_pvl : str
           path to a pvl file containing output from the ISIS camrange program

    Returns
    -------
    minlon,
    minlat,
    maxlon,
    maxlat : list
             Coordinates of the MBR in "Lower Left, Upper Right" (LLUR) order

    """
    minlat = float(isis.getkey(from_=camrange_pvl, grpname="UniversalGroundRange", keyword="MinimumLatitude").decode().replace('\n', ''))
    maxlat = float(isis.getkey(from_=camrange_pvl, grpname="UniversalGroundRange", keyword="MaximumLatitude").decode().replace('\n', ''))
    minlon = float(isis.getkey(from_=camrange_pvl, grpname="PositiveEast180", keyword="MinimumLongitude").decode().replace('\n', ''))
    maxlon = float(isis.getkey(from_=camrange_pvl, grpname="PositiveEast180", keyword="MaximumLongitude").decode().replace('\n', ''))

    return minlon,minlat,maxlon,maxlat

def stereo_mbr(minlongs,minlats,maxlongs,maxlats,buff=0.0):
    """
    Compute a minimum bounding rectangle of the intersection of multiple overlapping rectangles.
    This is useful for taking the MBRs of images in a stereopair and determining the MBR of the stereo coverage.
    Input coordinates are assumed to be latitudes and longitudes in degrees.


    Parameters
    ----------
    minlongs : list
               Minimum longitudes to consider

    minlats  : list
               Minimum latitudes to consider

    maxlongs : list
               Maximum latitudes to consider

    maxlats  : list
               Maximum latitudes to consider

    buff     : float
               Optional keyword to apply a buffer to each of the input coordinates.
               Can be positive or negative.
               Defaults to 0.0. 

    Returns
    -------
    minlon,
    minlat,
    maxlon,
    maxlat : list
             Coordinates of the intersection MBR in "Lower Left, Upper Right" (LLUR) order

    """

    # Compute min/max latitude of stereo coverage
    # Buffer stereo MBR by 0.5 degrees (clamping within known lat/long bounds of MOLA grid)
    minlon = max( (max(minlongs)-buff ), -180 )
    minlat = max( (max(minlats)-buff ),   -88 )
    maxlon = min( (min(maxlongs)+buff ),  180 )
    maxlat = min( (min(maxlats)+buff ),    88 )

    # Return values in "LLUR" order for easy use in gdal.Warp()
    return minlon,minlat,maxlon,maxlat


def main(user_args):

    project_name = user_args.project_name
    noproj_cubes = user_args.noproj_cube
    print(user_args)

    gdal.UseExceptions()
    ogr.UseExceptions()

    # Run campt
    for i in noproj_cubes:
        # Note output file name is based on first 15 characters of infile, which *should* capture full HiRISE ID
        # Why? "Because that's the way we've always done it!"
        # Write campt output to same directory as input images for legacy compatibility
        campt_out = os.path.join(os.path.dirname(i), 'campt_' + os.path.basename(os.path.splitext(i)[0])[0:15] + '.prt'  )
        try:
            isis.campt(from_=i, to=campt_out)
        except ProcessError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
            

    # Run camrange on each input cube
    camrange_pvl = [os.path.splitext(x)[0] + '_camrange.txt' for x in noproj_cubes]
    camrange_dict = dict(zip(noproj_cubes,camrange_pvl))
        
    for k,v in camrange_dict.items():
        try:
            isis.camrange(from_=k, to=v)
        except ProcessError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        
    img_minlats = []
    img_maxlats = []
    img_minlongs = []
    img_maxlongs = []

    # Figure out MBR of stereo coverage
    for i in camrange_pvl:
        minlon,minlat,maxlon,maxlat = camrange_mbr(i)
        if (minlon == -180) and (maxlon == 180):
            print("\nWARNING: " + i + " crosses the 180 degree longitude line. \n")
            
        img_minlongs.append(minlon)
        img_minlats.append(minlat)
        img_maxlongs.append(maxlon)
        img_maxlats.append(maxlat)

        # Delete the camrange file
        os.remove(i)

    # Compute min/max latitude of stereo coverage
    # Buffer stereo MBR by 0.5 degrees (clamping within known lat/long bounds of MOLA grid)
    stereo_minlon, stereo_minlat, stereo_maxlon, stereo_maxlat = stereo_mbr(img_minlongs,
                                                                            img_minlats,
                                                                            img_maxlongs,
                                                                            img_maxlats,
                                                                            buff=0.5)
    
    # Done with ISIS, rename print.prt for legacy compatibility
    os.replace('print.prt', 'hidata4gxp.prt')

    print(stereo_minlat,stereo_maxlat,stereo_minlon,stereo_maxlon)

    # @TODO Delete this debug block before committing
    ### DEBUG ###
    # Mocking extent for testing
    # stereo_minlon = float(-10.5)
    # stereo_minlat = float(-10.5)
    # stereo_maxlon = float(10.5)
    # stereo_maxlat = float(10.5)
    #############

    # Stereo coverage that straddles +/-180 degrees longitude is currently unsupported
    if (minlon == -180) and (maxlon == 180):
        print("\nERROR: Unable to compute longitude bounds of stereo coverage. \nAll images cross the 180 degree longitude line. \n")
        sys.exit(1)

    # Create directory to hold MOLA grid
    if not os.path.exists('MOLA_DEM'):
        os.mkdir('MOLA_DEM')

    # @TODO Things like paths to reference data should be stored in a config.py file and imported
    # mola_delta_radius_iau = '/scratch/dpmayer/APPL-Tools_dev/mola_256ppd_latlon_88lat_DeltaRadiusIAUSphere.tif'
    
    # Get spatial reference object defining a geographic SRS for Mars based on mola_delta_radius_iau
    mola_ds = gdal.Open(mola_delta_radius_iau)
    tsrs = mola_ds.GetSpatialRef()
    mola_ds = None
    # Set width and height (in pixels) of output at 256ppd, rounding to nearest 0.125 degrees (=32 pixels)
    w = 32 * round( (abs(stereo_maxlon - stereo_minlon) * 256) / 32)
    h = 32 * round( (abs(stereo_maxlat - stereo_minlat) * 256) / 32)
    wopts = gdal.WarpOptions(format="GTiff", \
                             dstSRS=tsrs, \
                             outputBounds=(stereo_minlon, stereo_minlat, stereo_maxlon, stereo_maxlat), \
                             width=w, \
                             height=h)
    # Run gdal.Warp()
    mola_output = ('MOLA_DEM/' + project_name + '_mola.tif')
    gdal.Warp(mola_output, mola_delta_radius_iau, options=wopts)

    # Extract the elevation range of within the stereo coverage MBR, buffered by 0.1 degrees
    #  that is, apply a *negative* 0.4 degree buffer to the (previously buffered) stereo coverage MBR
    topts = gdal.TranslateOptions(format="VRT", \
                                  projWin=[stereo_minlon+0.4, stereo_maxlat-0.4, stereo_maxlon-0.4, stereo_minlat-0.4])
    mem_subset = ('/vsimem/' + project_name + '_stats.vrt')
    gdal.Translate(mem_subset, mola_output, options=topts)

    iopts = gdal.InfoOptions(format='json', computeMinMax=True, showRAT=False)
    info_out = gdal.Info(mem_subset, options=iopts)
    # Round min and max elevation to nearest 100 meters
    minZ = 100 * round(info_out['bands'][0]['computedMin'] / 100)
    maxZ = 100 * round(info_out['bands'][0]['computedMax'] / 100)

    gdal.Unlink(mem_subset)

    # If this particular area of the MOLA grid is flat add 100 m to maxZ
    # Why? "Because that's the way we've always done it!"
    if minZ == maxZ :
        maxZ = maxZ + 100.0

    print("minZ: ", minZ)
    print("maxZ: ", maxZ)

    # Calculate reference point, rounded to nearest 0.1 degrees and converted to DMS
    rlat = round( (((stereo_maxlat - stereo_minlat)/2) + stereo_minlat )* 10)/10
    rlon = round( (((stereo_maxlon - stereo_minlon)/2) + stereo_minlon )* 10)/10
    rlat = dd2dms(rlat)
    rlon = dd2dms(rlon)
    
    project_stats = project_name + '_GXP_statistics.lis'
    write_hidata_stats(rlat,rlon,minZ,maxZ,project_stats)

    ### MOLA PEDR extraction ###
    # 1. Build PEDR2TAB.PRM file with stereo MBR from above
    # Create directory to hold MOLA shot data
    if not os.path.exists('MOLA_TRACKS'):
        os.mkdir('MOLA_TRACKS')
        
    pedr2tab_prm(stereo_minlon,stereo_minlat,stereo_maxlon,stereo_maxlat,
                 flags=['T','T','F','T','T','F','F','F','F','F','T','T','T'],
                 out=(project_name + ".tab"),
                 f=169.8944472236118)

    # 2. Run pedr2tab
    # @TODO Things like paths to reference data should be stored in a config.py file and imported
    # pedr_list = '/scratch/dpmayer/GLOBAL_MOLA_PEDR/pedr_list.lis'
    run_pedr2tab([pedr_list])

    # 3. Read PEDR output into pandas DataFrame and do some conditioning
    pedr = pedrtab2df(project_name + '.tab')
    # Convert longitudes to +/-180 domain
    pedr['long_East'] = pedr['long_East'].apply(lambda x: ((x + 180) % 360) - 180 )
    # Convert values in the "planet_rad" column to delta radius, IAU sphere by subtracting 3396190 meters
    pedr['planet_rad'] = pedr['planet_rad'].apply(lambda x: x - 3396190)
    pedr.rename(columns={'planet_rad':'DeltaR_IAU'}, inplace = True)
    # Force original precision of EphemerisTime
    pedr['EphemerisTime'] = pedr['EphemerisTime'].map(lambda x: '{0:.5f}'.format(x))
    
    # Set up paths of output files to go to MOLA_TRACKS directory
    pedr_tab = os.path.join('MOLA_TRACKS', project_name + '.tab')
    pedr_csv = os.path.join('MOLA_TRACKS', project_name + '.csv')
    pedr_prj = os.path.join('MOLA_TRACKS', project_name + '.prj')
    pedr_shp = os.path.join('MOLA_TRACKS', project_name + '_Z.shp')

    # Move the PEDR table and PRM file into MOLA_TRACKS directory
    os.replace(project_name + '.tab',pedr_tab)
    os.replace('PEDR2TAB.PRM',os.path.join('MOLA_TRACKS','PEDR2TAB.PRM'))

    # 4. Write PEDR DataFrame to CSV
    pedr.to_csv(path_or_buf=(pedr_csv), header=True, index=False)

    # 5. Create VRT to go with the CSV, use hard-coded SRS (with vertical datum)
    # This is not OGC-compliant WKT, but it's what GXP requires
    wkt = """GEOGCS["GCS_Mars_Sphere_2000",
    DATUM["D_Mars_Sphere_2000",
        SPHEROID["Mars_Sphere_2000_IAU",3396190,0.0]],
    PRIMEM["Reference_Meridian",0.0],
    UNIT["Degree",0.0174532925199433]],
VERTCS["Mars_2000",
    DATUM["D_Mars_Sphere_2000",
        SPHEROID["Mars_Sphere_2000_IAU",3396190,0.0]],
    PARAMETER["Vertical_Shift",0.0],
    PARAMETER["Direction",1.0],
    UNIT["Meter",1.0]]"""
    
    try:
        with open(pedr_prj, 'w') as prj:
            p = prj.write(wkt)
            prj.close
    except:
        print("Error writing WKT file " + pedr_prj, file=sys.stderr)
        sys.exit(1)


    # Create dict of field names and their types for VRT file
    # Force EphemerisTime to type String as lazy way of avoiding nonsense warning from OGR later on
    fields = ['long_East','lat_North','topography','MOLArange','DeltaR_IAU','c','A','offndr',
              'EphemerisTime','areod_lat','areoid_rad','shot','pkt','orbit','gm']
    types = ['Real','Real','Real','Real','Real','Integer','Integer','Real',
             'String','Real','Real','Integer','Integer','Integer','Integer']
    field_dict = dict(zip(fields,types))

    pedr_vrt = pedrcsv2vrt(pedr_csv, pedr_prj, field_dict, x='long_East', y='lat_North', z='DeltaR_IAU')

    # 5. Convert VRT to shapefile using OGR
    in_ds = ogr.Open(pedr_vrt)
    ogr.GetDriverByName("ESRI Shapefile").CopyDataSource(in_ds, pedr_shp)
    in_ds = None
    # ogr silently drops the VERTCS part of the WKT,
    # so replace the .prj file associated with the shapefile with exact WKT we want
    os.replace(pedr_prj, os.path.splitext(pedr_shp)[0] + '.prj')

    os.remove(pedr_csv)
    os.remove(pedr_vrt)


if __name__ == "__main__":
    sys.exit(main(parse_args()))
