#!/usr/bin/env python3

import sys
import os
import argparse
import subprocess
import readline
import pandas as pd
import numpy as np
from plio.io.io_bae import read_gpf, save_gpf
from appl_tools.pedr import pedrtab2df
from appl_tools.surfacefit import run_pc_align, update_gpf, ascii_dtm2csv

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description = """This script aligns Tie Points from a Socet Set/Socet GXP Ground Point File (GPF) to a reference elevation data set 
by acting as a thin wrapper around the 'pc_align' program from the NASA Ames Stereo Pipeline. 
Typically, Tie Points are too sparse to be reliably aligned to a reference using the iterative closest points algorithm in pc_align. Therefore, this script allows pc_align 
to first be applied to a (potentially low-resolution) digital terrain model derived from the stereopair that corresponds to the GPF file. 
The resulting transformation matrix is applied to the Tie Points during a second call to pc_align.

The transformed latitude, longitude, and height values from the Tie Points are then written to a new GPF with their sigmas set equal to 1 and the "known" flag 
changed from "1" (Tie Point) to "3" (XYZ Control). Non-Tie Points from the original GPF are written to the new GPF with their "known" flags changed to "1." 
Tie Points from the original GPF that were not active ("stat" = 0) are copied "as-is" into the new GPF. The output GPF preserves the order of the ground points from the original GPF.

If it is desired to update all active points in the input GPF, use the '--all-points' flag. The modified points will still have their "known" flag set to "3" (XYZ Control) in the 
output GPF.

The Ames Stereo Pipeline program pc_align must be available in the user's path or somewhere else where Python can find it. 
More information about the Ames Stereo Pipeline is available on the project's Git repository: https://github.com/NeoGeographyToolkit/StereoPipeline""",
                                     epilog = """EXAMPLES:
                                     Align Tie Points from a HiRISE DTM in Socet's ASCII DTM format to a reference DTM in GeoTIFF format. 
The Socet ASCII DTM will be automatically converted to a pc_align-compatible CSV, but the user should specify either the datum or planetary radii that describe the 
surface that the Socet DTM's heights are referenced to. In the following example, the Socet DTM is referenced to the Mars 2000 ellipsoid.
    %(prog)s --radii 3396190 3376000 --max-displacement 50 CTX_reference_dtm.tif HiRISE_Gale_low_res.asc HiRISE_Gale.gpf output_HiRISE_Gale.gpf

                                     This script can be used to simulate the behavior of the legacy SurfaceFit Perl script wherein Socet Tie Points from a Mars DTM referenced to an ellipsoid 
are aligned to MOLA shot data referenced to the geoid, the "--max-displacement" parameter was fixed at 300 meters and the datum was set to the IAU sphere ("D_MARS"):
                                     %(prog)s --max-displacement 300 --datum D_MARS MOLA_reference.tab CTX_NE_Syrtis_low_res_aate.asc CTX_NE_Syrtis.gpf tfm_CTX_NE_Syrtis.gpf \n

""")
    parser.add_argument("ref_dtm",
                        help="The name of the file that contains the reference elevation data.")
    parser.add_argument("socet_dtm",
                        help = "The name of the file containing the Socet Set or GXP DTM to be aligned. Must be in ASCII format.")
    parser.add_argument("socet_gpf",
                        help = "The name of the Socet Ground Point File that will be updated using the transform that was calculated for socet_dtm.")
    parser.add_argument("tfm_socet_gpf",
                        help = """Name to use for the output (transformed) ground point file. Must include ".gpf" extension.""")
    parser.add_argument("--all-points",
                        action='store_true',
                        help = "This flag will force updating of all active (stat = 1) points in socet_gpf, not just tie points (known = 0).")
    parser.add_argument("--s_srs",
                        help = """PROJ string describing the projected spatial reference system of the input GPF. If omitted, script assumes a geographic SRS with shape defined by --datum or --radius. If ref_dtm is CSV, it must use same SRS as the GPF file.""",
                        nargs='?',
                        type=str)
    parser.add_argument("--gxp",
                        action='store_true',
                        help = "Flag to indicate input GPF is in Socet GXP format. Output GPF will be in legacy Socet Set format.")
    parser.add_argument("--max-displacement",
                        type=float,
                        nargs=1,
                        help="Maximum expected displacement of source points as result of alignment, in meters (after the initial guess transform is applied to the source points). Used for removing gross outliers in the source (movable) pointcloud.")
    refshape = parser.add_mutually_exclusive_group(required=True)
    refshape.add_argument("--datum",
                        nargs=1,
                        choices=['D_MARS', 'D_MOON', 'MOLA', 'NAD27', 'NAD83', 'WGS72', 'WGS_1984'],
                        help = """Use this datum for heights in the input GPF file and any other input CSV files.""")
    refshape.add_argument("--radii",
                          nargs=2,
                          metavar=('semi-major-axis','semi-minor-axis'),
                          type=float,
                          help="""Semi-major and semi-minor axes, expressed in meters, that define the ellipsoid that heights in the input GPF file and any other input CSV files are referenced to.""")
    parser.add_argument('pc_align_args',
                        nargs = argparse.REMAINDER,
                        help = """Additional arguments that will be passed directly to pc_align.""")
    args = parser.parse_args()
    return args

def main(user_args):

    ref_dtm = user_args.ref_dtm
    # ref_format = user_args.ref_format
    socet_dtm = user_args.socet_dtm
    # socet_format = user_args.socet_format
    socet_gpf = user_args.socet_gpf
    tfm_socet_gpf = user_args.tfm_socet_gpf
    all_points = user_args.all_points
    datum = user_args.datum
    radii = user_args.radii
    max_displacement = user_args.max_displacement
    pc_align_args = user_args.pc_align_args
    s_srs = user_args.s_srs
    gxp = user_args.gxp

    if os.path.splitext(tfm_socet_gpf)[1] != ".gpf":
        print("""USER ERROR: Output file name must use ".gpf" extension""")
        sys.exit(1)

    ref_basename = os.path.splitext(ref_dtm)[0]
    ref_ext = os.path.splitext(ref_dtm)[1]
    socet_dtm_basename = os.path.splitext(socet_dtm)[0]
    src_ext = os.path.splitext(socet_dtm)[1]

    if ref_ext.lower() == '.tab':
        print("\n\n *** WARNING: Using MOLA heights above geoid ***\n\n")
        ref_dtm_pc_align = (ref_basename + "_RefPC.csv")
        pedr_df = pedrtab2df(ref_dtm)
        # Assume ographic lat, lon, topo columns exist
        pedr_df.to_csv(path_or_buf=(ref_dtm_pc_align), header=False, index=False,
                       columns=['areod_lat','long_East','topography'])
    elif ref_ext.lower() == '.asc':
        ref_dtm_pc_align = (ref_basename + "_RefPC.csv")
        ascii_dtm2csv(ref_dtm, ref_dtm_pc_align)
    elif ref_ext.lower() == '.csv':
        ref_dtm_pc_align = ref_dtm
    else:
        # assume raster and let pc_align complain if it's not
        ref_dtm_pc_align = ref_dtm

    if src_ext.lower() == '.asc':
        socet_dtm_pc_align = (socet_dtm_basename + ".csv")
        ascii_dtm2csv(socet_dtm,socet_dtm_pc_align)
    else:
        # assume raster and let pc_align complain if it's not
        socet_dtm_pc_align = socet_dtm

    # Read in the Socet ground point file using plio's read_gpf()
    if gxp:
        gpf_df = read_gpf(socet_gpf, gxp=True)
        # Modify DataFrame to resemble legacy Socet Set format
        # Rename "use" and "point_type" to their Socet Set equivalents
        gpf_df.rename(columns={'use':'stat', 'point_type':'known'}, inplace=True)
        if not s_srs:
            gpf_df.lat_Y_North = np.radians(gpf_df['lat_Y_North'])
            gpf_df.long_X_East = np.radians(((gpf_df['long_X_East'] + 180) % 360) - 180)
    else:
        gpf_df = read_gpf(socet_gpf)

    # Set the index of the GPF dataframe to be the point_id column
    gpf_df.set_index('point_id', drop=False, inplace=True)

    # If user passed "--all-points" option, copy *all active* points to new data frame
    #  Otherwise, copy active tie points (point_type == 0) only
    # Note that DataFrame is named "tp_df" regardless of whether it includes only tiepoints or not
    if all_points:
        tp_df =  gpf_df[(gpf_df.stat == 1)].copy()
    else:
        tp_df = gpf_df[(gpf_df.known == 0) & (gpf_df.stat == 1)].copy()
            
    if not s_srs:
        tp_df.lat_Y_North = np.degrees(tp_df.lat_Y_North)
        tp_df.long_X_East = ((360 + np.degrees(tp_df.long_X_East)) % 360)

    align_prefix = (socet_dtm_basename + '_pcAligned_DTM')
    gpf_align_prefix = (socet_dtm_basename + '_pcAligned_gpfTies')

    # Build arguments list and perform alignment with pc_align
    align_args = ["--max-displacement", str(max_displacement[0]),
                  "--save-inv-transformed-reference-points",
                  "-o", align_prefix]
    
    # Extend the list of arguments for pc_align to include the datum or radii as necessary
    if datum is not None:
        align_args.extend(["--datum", str(datum[0])])
    elif radii is not None:
        align_args.extend(["--semi-major-axis", str(radii[0]), "--semi-minor-axis", str(radii[1])])

    # If the user passed additional arguments for pc_align, extend align_args to include them
    if pc_align_args:
        align_args.extend(pc_align_args)
        
    # Extend the list to place point clouds at the end of the list of arguments for pc_align
    align_args.extend([socet_dtm_pc_align, ref_dtm_pc_align])

    print("Aligning " + socet_dtm_pc_align + " to " + ref_dtm_pc_align)
    try:
        run_align = run_pc_align(align_args)
    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(1)
    
    # Write out CSV (compatible with pc_align) containing lat/long/height of points to be updated
    socet_gpf_csv = ((os.path.splitext(socet_gpf)[0]) + '.csv')
    tp_df.to_csv(path_or_buf=socet_gpf_csv,
                 header=False,
                 index=False,
                 columns=['lat_Y_North','long_X_East','ht'])

    # Build arguments list and apply transformation to selected points from GPF using pc_align
    # Set num-iterations = 0 because only going to apply existing transform
    transform_matrix = (align_prefix + '-inverse-transform.txt')
    apply_tfm_args = ["--initial-transform",transform_matrix,
                      "--num-iterations","0",
                      "--max-displacement", str(max_displacement[0]),
                      "--save-transformed-source-points",
                      "-o", gpf_align_prefix ]
    
    # Extend the list of arguments for pc_align to include the datum or radii as necessary
    if datum is not None:
        apply_tfm_args.extend(["--datum", str(datum[0])])
    elif radii is not None:
        apply_tfm_args.extend(["--semi-major-axis", str(radii[0]), "--semi-minor-axis", str(radii[1])])

    if s_srs:
        apply_tfm_args.extend(["--csv-proj4", str(s_srs)])
        apply_tfm_args.extend(["--csv-format", str('''2:easting 1:northing 3:height_above_datum''')])

    # Extend the list to place point clouds at the end of the list of arguments for pc_align
    apply_tfm_args.extend([ref_dtm_pc_align,socet_gpf_csv])

    # Apply transform from previous pc_align run to tie points CSV
    print("Calling pc_align with 0 iterations to apply transform from previous run to Tie Points from GPF")
    try:
        run_align = run_pc_align(apply_tfm_args)
    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(1)

    # mergeTransformedGPFTies
    # Convert the transformed tie points from CSV to a pandas DataFrame
    t = np.genfromtxt((gpf_align_prefix + '-trans_source.csv'),delimiter=',',
                      skip_header=3,dtype='unicode')
    id_list = tp_df['point_id'].tolist()
    tfm_index = pd.Index(id_list)
    tfm_tp_df = pd.DataFrame(t, index=tfm_index, columns=['lat_Y_North','long_X_East','ht'])
    tfm_tp_df = tfm_tp_df.apply(pd.to_numeric)

    # Update the original tiepoint DataFrame with the transformed lat/long/height values from pc_align
    print("Updating GPF coordinates")
    tp_df.update(tfm_tp_df)

    # Convert long from 0-360 to +/-180 and convert lat/long to radians
    # Note: Even if gxp==True, plio only knows how to write legacy Socet Set-style GPFs,
    #  so must convert to radians on output if not s_srs
    if not s_srs:
        tp_df.lat_Y_North = np.radians(tp_df['lat_Y_North'])
        tp_df.long_X_East = np.radians(((tp_df['long_X_East'] + 180) % 360) - 180)

    # Apply updates to the original GPF DataFrame, and save transformed GPF file
    update_gpf(gpf_df,tp_df,tfm_socet_gpf,all_pts=all_points)

    # Write list of pointIDs of the transformed tiepoints to a file
    # Included for legacy compatibility, not actually used for anything
    tp_df.to_csv(path_or_buf=((os.path.splitext(socet_gpf)[0]) + '.tiePointIds.txt'),
                 sep=' ', header=False,
                 index=False,
                 columns=['point_id'])


if __name__ == "__main__":
    sys.exit(main(parse_args()))
