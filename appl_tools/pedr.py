from os import path
import subprocess
import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree

def pedr2tab_prm(minlon,minlat,maxlon,maxlat,flags=['T','T','F','T','T','F','F','F','F','F','T','T','T'],out=None,f=169.8944472236118):
    """
    Helper function to build a PEDR2TAB.PRM file to be read by the fortran program "pedr2tab."
    The format of the parameter file required by "pedr2tab" is arcane, so the way we build it with Python is a little ugly.

    Parameters
    ----------
    minlon   : float
               Minimum longitude of bounding rectangle. [0-360] domain, positive east

    minlat   : float
               Minimum planetocentric latitude of bounding rectangle

    maxlon   : float
               Maximum longitude of bounding rectangle. [0-360] domain, positive east

    maxlat   : float
               Minimum planetocentric latitude of bounding rectangle

    flags    : list
               List containing sequence of the letters "T" and/or "F" to indicate whether flag in PEDR2TAB.PRM
               is true or false. See the "pedr2tab" documentation [sic] for details of what these do.

    out      : str
               Name of file that "pedr2tab" should write results to if OneBigFile flag is set to T

    f        : float
               (Inverse) flattening to use for computing planetographic latitudes. Defaults to IAU2000 value
               f = 1/((a-b)/a)
               where a = 3396190 meters, b = 3376200 meters


    Returns
    -------
    None

    """

    # Make sure longitudes are in [0-360] domain
    minlon = ((360 + minlon) % 360)
    maxlon = ((360 + maxlon) % 360)

    # Format big multi-line string
    p = """{} # lhdr
{} # 0: shot longitude, latitude, topo, range, planetary_radius,ichan,aflag
{} # 1: MGS_longitude, MGS_latitude, MGS_radius
{} # 2: offnadir_angle, EphemerisTime, areodetic_lat,areoid
{} # 3: ishot, iseq, irev, gravity model number
{} # 4: local_time, solar_phase, solar_incidence
{} # 5: emission_angle, Range_Correction,Pulse_Width_at_threshold,Sigma_optical,E_laser,E_recd,Refl*Trans
{} # 6: bkgrd,thrsh,ipact,ipwct
{} # 7: range_window, range_delay
{} #   All shots, regardless of shot_classification_code
{} # F = noise or clouds, T = ground returns
{} # do crossover correction
{} \"{out}\" # OneBigFile, output file template(must be enclosed in quotes).

{minlon}   # ground_longitude_min
{maxlon}   # ground_longitude_max
{minlat}   # ground_latitude_min
{maxlat}     # ground_latitude_max

{f}	# flattening used to compute areographic ("areodetic") latitudes
""".format(*flags,minlon=minlon,maxlon=maxlon,minlat=minlat,maxlat=maxlat,out=out,f=f)

    try:
        with open('PEDR2TAB.PRM', 'w') as prm:
            r = prm.writelines(p)
            prm.close
    except:
        print("Error writing pedr2tab parameter file, PEDR2TAB.TAB", file=sys.stderr)
    
    return

def run_pedr2tab(pedrlist):
    """
    Use subprocess to call the external program, "pedr2tab."
    Relies on the external program to decide if arguments are valid or not.
    Pipe STDERR to STDOUT.


    Parameters
    ----------
    pedrlist   : str
                 path to file containing list of PEDR binaries

    """

    cmd_args = ["pedr2tab", pedrlist]
    result = subprocess.run(cmd_args,check=True,stderr=subprocess.STDOUT,encoding='utf-8')

    return result

def pedrtab2df(table,cols=None):
    """
    Read a MOLA PEDR table file into a pandas data frame.


    Parameters
    ----------
    table   : str
              path to the input MOLA PEDR table from pedr2tab

    cols    : list
              Optional list of column headings. Should only be used if table doesn't contain headers.
              Useful if the PEDR table was created with lhdr flag set to False in PEDR2TAB.PRM.

    Returns
    -------
    df :  DataFrame
                

    """

    # column names not specified, infer them from first line, and plan to skip first 2 lines when writing to CSV
    if not cols:
        cols = np.genfromtxt(table, max_rows = 1, dtype='unicode')
        skip = 2
    else:
        skip = 0
        
    d = np.genfromtxt(table, skip_header=skip, dtype='unicode')
    df = pd.DataFrame(d, columns=cols)
    df = df.apply(pd.to_numeric)
    
    return df

def pedrcsv2vrt(csv,prj,fields,x=None,y=None,z=None):
    """
    Build a vector VRT file that describes a CSV of PEDR data


    Parameters
    ----------
    csv     : str
              Path to the CSV to build a VRT for

    prj     : str
              Path to file containing WKT of desired SRS

    fields  : dict
              Field names and their type (Integer, Real, String, etc.)

    x       : str
              Name of the field that holds x coordinates

    y       : str
              Name of the field that holds y coordinates

    z       : str
              Name of the field that holds z coordinates

    Returns
    -------
    outvrt  : str
              Path to the output VRT. Takes basename and dirname from input csv
                

    """
    outvrt = path.splitext(csv)[0] + '.vrt'
    
    vrt = ET.Element('OGRVRTDataSource')
    layer = ET.SubElement(vrt,'OGRVRTLayer')
    layer.set('name', path.basename(path.splitext(csv)[0]) )
    ET.SubElement(layer,'SrcDataSource').text = csv
    ET.SubElement(layer,'LayerSRS').text = prj
    ET.SubElement(layer,'GeometryType').text = 'wkbPoint'
    geom_field = ET.SubElement(layer,'GeometryField')
    geom_field.set('encoding','PointFromColumns')
    geom_field.set('x', x)
    geom_field.set('y', y)
    geom_field.set('z', z)

    for k,v in fields.items():
        field = ET.SubElement(layer,'Field')
        field.set('name',k)
        field.set('src',k)
        field.set('type',v)

    ElementTree(vrt).write(outvrt)

    return outvrt

