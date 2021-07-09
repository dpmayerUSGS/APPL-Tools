#!/usr/bin/env python3
import sys
import os
from os import path
import glob
import argparse
from osgeo import ogr, osr
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree
from appl_tools.pedr import pedrcsv2vrt

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""Convert ODE created MOLA, LOLA, or MLA shot data to ESRI Shapefile.
        The CSV is expected to be downloaded from the ODE REST service, possibly via the script ode_get_laser_alt.py""",
        epilog="""EXAMPLES:
        MOLA using planetographic latitudes and elevations relative to biaxial ellipsoid (a=3396190 meters, b=3376200 meters):
        %(prog)s mars --ographic ode_molardr.csv \n

        MOLA using planetocentric latitudes and elevations relative to geoid:
        %(prog)s mars --geoid ode_molardr.csv \n

        LOLA using planetocentric latitudes and heights relative to IAU sphere (1737400 meters)
        %(prog)s moon ode_lolapedr.csv \n

        If user's shell supports globstar or other forms of expansion, it is possible to pass more than one file into the script:
        %(prog)s mercury "*_pts_csv.csv" \n

        Use the --force-3d option to create a shapefile with a Geographic 3D CRS for use in Socet Set or GXP.
        PROJ will print an error message about being unable to export the CRS, but this message can be ignored.
        %(prog)s mars ode_molardr.csv --force-3d \n
    
    """)
    
    parser.add_argument('target', choices=["mars","moon","mercury"], 
                        type = str.lower, 
                        help="Specify which target: mars, moon, or mercury")
    parser.add_argument('--ographic', action="store_true", default=False,
                        help='Convert planetocentric latitudes to planetographic. Ignored for Moon and Mercury')
    parser.add_argument('--geoid', action="store_true", default=False,
                        help='Use heights relative to geoid rather than heights relative to spheroid for Z values in shapefile. Ignored for Mercury.')
    parser.add_argument('--force-3d', action="store_true", default=False,
                        help="""Force output shapefiles to use a geographic 3D CRS, even though PROJ doesn't want to. If this option is invoked, PROJ will print an error, but the script will override the .prj file associated with the output shapefile.""")
    parser.add_argument('files',
                        nargs='+',
                        help="One or more files to process")
    
    args = parser.parse_args()
    return args

def csv2vrt(csv,prj,field_dict,x=None,y=None,z=None):
    """
    Build a vector VRT file that describes a CSV of PEDR data


    Parameters
    ----------
    csv     : str
              Path to the CSV to build a VRT for

    prj     : str
              Path to file containing WKT of desired SRS

    field_dict  : dict
              Field names as keys and nested dict attribute name:values as values

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
    # Hard-coded to 3D ("2.5D") point
    ET.SubElement(layer,'GeometryType').text = 'wkbPoint25D'
    geom_field = ET.SubElement(layer,'GeometryField')
    geom_field.set('encoding','PointFromColumns')
    geom_field.set('x', x)
    geom_field.set('y', y)
    geom_field.set('z', z)

    for k,v in field_dict.items():
        field = ET.SubElement(layer,'Field')
        field.set('name',k)
        field.set('src',k)
        # Unpack field attributes
        for i,j in v.items():
            field.set(i,j)

    ElementTree(vrt).write(outvrt)

    return outvrt

def main(user_args):
    target = user_args.target
    ographic = user_args.ographic
    geoid = user_args.geoid
    force_3d = user_args.force_3d
    
    # Guarantee list of files is unique
    files = list(dict.fromkeys(user_args.files))

    # 0. Set some target-specific variables, override commandline options if not applicable to target
    if target == 'mars':
        fields = ['LONG_EAST','LAT_NORTH','TOPOGRAPHY','MOLA_RANGE','PLANET_RAD',
                  'C','A','EPHEM_TIME','UTC','ORBIT']
        df_types = ['float', 'float', 'float', 'float', 'float',
                    'int', 'int', 'float', 'string', 'int']
        # Dict of VRT attribute:values for each field. Should at least have 'type'
        vrt_attribs = [{'type':'Real', 'width':'9','precision':'5'},
                       {'type':'Real', 'width':'8','precision':'5'},
                       {'type':'Real', 'width':'10','precision':'2'},
                       {'type':'Real', 'width':'10', 'precision':'2'},
                       {'type':'Real', 'width':'10', 'precision':'2'},
                       {'type':'Integer','width':'1'},
                       {'type':'Integer','width':'1'},
                       {'type':'Real','width':'20','precision':'5'},
                       {'type':'String'},
                       {'type':'Integer','width':'9'}]
        semimajor = 3396190.0
        if ographic:
            targetWKT = "Mars"
            semiminor = 3376200.0
            # Inverse of the first flattening, a.k.a. "inverse f"
            invf = semimajor / (semimajor - semiminor)
            # ellipticity
            ell = np.sqrt( (semimajor**2 - semiminor**2)/(semimajor**2) )
        else:
            targetWKT = "Mars_Sphere"
            semiminor = semimajor
            invf = 0.0
        year = 2000
        x = 'LONG_EAST'
        y = 'LAT_NORTH'
    elif target == 'mercury':
        ographic = False
        geoid = False
        fields = ['longitude','latitude','altitude','radius','Ephem_Time','MET',
                  'frm','chn','Pulswd','thrsh','gain','1way_range','Emiss','TXmJ',
                  'UTC','TOF_ns_ET','Sat_long','Sat_lat','Sat_alt','Offnad','Phase',
                  'Sol_inc','SCRNGE','seqid','Product_id']
        df_types = ['float','float','float','float','float','int',
                 'int','int','float','float','float','float','float','float',
                 'string','float','float','float','float','float','float',
                 'float','int','int','string']
        # Dict of VRT attribute:values for each field. Should at least have 'type'
        vrt_attribs = [{'type':'Real', 'width':'9','precision':'5'},
                       {'type':'Real', 'width':'10','precision':'5'},
                       {'type':'Real'},{'type':'Real'},{'type':'Real', 'width': '24', 'precision':'6'},
                       {'type':'Integer', 'width':'10'},{'type':'Integer','width':'1'},
                       {'type':'Integer','width':'1'},{'type':'Real','width':'6', 'precision':'1'},
                       {'type':'Real', 'width':'7', 'precision':'4'},
                       {'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},
                       {'type':'String'},{'type':'Real'},{'type':'Real'},
                       {'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},
                       {'type':'Real'},{'type':'Integer'},{'type':'Integer'},{'type':'String'}]
        targetWKT = "Mercury"
        semimajor = semiminor = 2439400.0
        invf = 0.0
        year = 2015
        x = 'longitude'
        y = 'latitude'
    elif target == 'moon':
        ographic = False
        fields = ['UTC','Pt_Long','Pt_Lat','Pt_Radius',
                  'Pt_Range','Pt_PulseW','Pt_Energy','Pt_noi','Pt_Thr','Pt_Gn','Flg','S',
                  'Frm','Mission_ET','Subseconds','TerrDynTim','TX_E_mJ',
                  'TX_PulseW','SC_Long','SC_Lat','SC_radius','Geoid','Offnadir',
                  'Emission','Sol_INC','Sol_Phs','EarthCentr','Earth_PW','Earth_E.']
        df_types = ['string','float','float','float',
                 'float','float','float','float','float','float','int','int',
                 'int','float','float','float','float',
                 'float','float','float','float','float','float',
                 'float','float','float','float','float','float']
        vrt_attribs = [{'type':'String'},{'type':'Real','width':'9','precision':'5'},{'type':'Real','width':'9','precision':'5'},
                       {'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},
                       {'type':'Real'},{'type':'Integer','width':'4'},{'type':'Integer','width':'1'},
                       {'type':'Integer','width':'3'},{'type':'Real'},{'type':'Real'},{'type':'Real','width':'19','precision':'9'},
                       {'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},
                       {'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},{'type':'Real'},
                       {'type':'Real'},{'type':'Real'},{'type':'Real'}]
        targetWKT = "Moon"
        semimajor = semiminor = 1737400.0
        invf = 0.0
        year = 2000
        x = 'Pt_Long'
        y = 'Pt_Lat'

    df_dict = dict(zip(fields,df_types))
    field_dict = dict(zip(fields,vrt_attribs))

    if force_3d:
        # pseudo-ESRI-style WKT1 describing 3D Geographic CRS
        # put on a single line
        wkt = """GEOGCS["GCS_{0}_{1}",DATUM["D_{0}_{1}",SPHEROID["{0}_{1}",{2:.1f},{3:.14f}]],PRIMEM["Reference Meridian",0.0],UNIT["Degree",0.0174532925199433]], VERTCS["{0}_{1}",DATUM["D_{0}_{1}", SPHEROID["{0}_{1}",{2:.1f},{3:.14f}]],PARAMETER["Vertical_Shift",0.0],PARAMETER["Direction",1.0],UNIT["Meter",1.0]]""".format(targetWKT,year,semimajor,invf)
    else:
        # 2D WKT2
        wkt = """GEOGCRS["GCS_{0}_{1}",
        DATUM["D_{0}_{1}",
            ELLIPSOID["{0}_{1}_IAU",{2:.1f},{3:.14f},
                LENGTHUNIT["metre",1]]],
        PRIMEM["Reference_Meridian",0,
            ANGLEUNIT["degree",0.0174532925199433]],
        CS[ellipsoidal,2],
            AXIS["geodetic latitude (Lat)",north,
                ORDER[1],
                ANGLEUNIT["degree",0.0174532925199433]],
            AXIS["geodetic longitude (Lon)",east,
                ORDER[2],
                ANGLEUNIT["degree",0.0174532925199433]]]""".format(targetWKT,year,semimajor,invf)

    # Loop over files and harmonize latitudes, elevations as appropriate
    for infile in files:
        wktfile = os.path.splitext(infile)[0] + '_tmp.prj'
        outshp = os.path.splitext(infile)[0] + '.shp'

        # Write WKT file
        try:
            with open(wktfile, 'w') as prj:
                p = prj.write(wkt)
                prj.close
        except:
            print("Error writing WKT file " + wktfile, file=sys.stderr)

        # Read CSV into pandas DataFrame
        d = np.genfromtxt(infile, skip_header=1, delimiter=',', dtype='unicode')
        df = pd.DataFrame(d, columns=fields)
        df = df.astype(df_dict)

        # Update field_dict and mappings for writing VRT later
        if ographic:
            field_dict['OG_Lat'] = {'type':'Real','width':'8','precision':'5'}
            y = 'OG_Lat'
            
        if geoid:
            field_dict['DelGeoid_m'] = {'type':'Real','width':'10','precision':'2'}
            z = 'DelGeoid_m'
        else:
            field_dict['DelRad_m'] = {'type':'Real','width':'10','precision':'2'}
            z = 'DelRad_m'

        # Modify longitudes in-place to +/- 180 domain
        df[x] = df[x].apply(lambda lon: ((lon + 180) % 360) - 180 )

        # The rest of the loop is a mess and I hate it
        
        # Convert kilometers to meters
        if target == 'mercury':
            df = df.assign(DelRad_m=df['altitude'] * 1000)
        elif target == 'moon':
            if geoid:
                df = df.assign(DelGeoid_m=df['Geoid'] * 1000)
            else:
                df = df.assign(DelRad_m=df['Pt_Radius'] * 1000)

        # 4 possible combinations of ographic and geoid for Mars
        if target == 'mars':
            if not ographic and not geoid:
                df = df.assign(DelRad_m=df['PLANET_RAD'] - semimajor)
            if geoid:
                df = df.assign(DelGeoid_m=df['TOPOGRAPHY'])
            if ographic:
                # convert latitudes to ographic and store in 'OG_Lat' field
                df = df.assign(OG_Lat= np.degrees( np.arctan( np.arctan(np.radians(df['LAT_NORTH'])) / (1 - (1/invf))**2) ) )
                if not geoid:
                    # delta radius is relative to biaxial ellipsoid
                    df = df.assign(DelRad_m=df['PLANET_RAD'] - (semimajor / (np.sqrt(1 + (ell**2/(1-ell**2)) * np.sin(np.radians(df['LAT_NORTH']))**2 ) ) ) )

        
        # Write modified DataFrame to temp CSV
        tmpcsv = os.path.splitext(infile)[0] + '_tmp.csv'
        df.to_csv(path_or_buf=tmpcsv, header=True, index=False)

        # Write vector VRT
        outvrt = csv2vrt(tmpcsv, wktfile, field_dict, x=x, y=y, z=z)

        # Convert VRT to shapefile
        in_ds = ogr.Open(outvrt)
        ogr.GetDriverByName("ESRI Shapefile").CopyDataSource(in_ds, outshp)
        in_ds = None

        if force_3d:
            # Overwrite the .prj file that OGR wrote for the Shapefile
            print("Forcing pseudo-ESRI-style WKT1 for 3D Geographic CRS")
            os.replace(wktfile, os.path.splitext(infile)[0] + '.prj')
        else:
            os.remove(wktfile)
            
        # Delete temp CSV, .vrt
        os.remove(tmpcsv)
        os.remove(outvrt)
        

if __name__ == "__main__":
    sys.exit(main(parse_args()))
