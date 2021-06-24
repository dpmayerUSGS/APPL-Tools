from os import path
import subprocess
import pandas as pd
import numpy as np
from plio.io.io_bae import read_gpf, save_gpf

def run_pc_align(args):
    """
    Use subprocess to call the external program, pc_align. Relies on
    pc_align to decide if arguments are valid or not.
    Pipe STDERR to STDOUT.


    Parameters
    ----------
    args : list
           list of arguments to be passed to pc_align

    """
    
    align_args = ["pc_align"]
    align_args.extend(args)
    run_align = subprocess.run(align_args,check=True,stderr=subprocess.STDOUT,encoding='utf-8')

    return run_align

def update_gpf(gpf_df,tp_df,outname,all_pts=False):
    """
    Update a GPF DataFrame with new lat/long/height values from another DataFrame,
    Change point types based on user input, and set sigmas of updated points == 1 meter.


    Parameters
    ----------
    gpf_df : pd.DataFrame
             Pandas DataFrame of a Socet GPF file. Format obtained from read_gpf(),
             and subsequently indexed on point_id field.

    tp_df : pd.DataFrame
            Pandas DataFrame of a Socet GPF file. Format obtained from read_gpf(),
            and subsequently indexed on point_id field. Should be (at least) a 
            subset of gpf_df

    outname: str
                   Path to the output GPF

    all_pts : boolean
                 If True, update all active points in gpf_df, regardless of point type.
                 If False, update only active tiepoints in gpf_df, and then change 
                     active non-tiepoints to tiepoints.


    """

    gpf_df.update(tp_df)

    ## Build boolean masks of gpf_df to enable selective updating of point types
    ## transformed tie point mask
    if all_pts:
        tfm_tp_mask = (gpf_df['stat'] == 1)
    else:
        ## non-tie point mask
        non_tp_mask = ((gpf_df['stat'] == 1) & (gpf_df['known'] > 0))
        tfm_tp_mask = ((gpf_df['stat'] == 1) & (gpf_df['known'] == 0))
        ## Change non-Tie Points to Tie Point
        gpf_df.loc[non_tp_mask, 'known'] = 0

    ## Change transformed Tie Points to XYZ Control, sigmas = 1.0, residuals = 0.0
    gpf_df.loc[tfm_tp_mask, 'known'] = 3
    gpf_df.loc[tfm_tp_mask, 'sig0':'sig2'] = 1.0
    gpf_df.loc[tfm_tp_mask, 'res0':'res2'] = 0.0

    ## Convert the 'stat' and 'known' columns to unsigned integers
    gpf_df.known = pd.to_numeric(gpf_df['known'], downcast = 'unsigned')
    gpf_df.stat = pd.to_numeric(gpf_df['stat'], downcast = 'unsigned')

    save_gpf(gpf_df, outname)

    return

def ascii_dtm2csv(ascii_dtm, outname):
    """
    Read an ASCII DTM from Socet Set into a pandas data frame,
    write out to CSV with latitude and longitude columns swapped
    to match the default format for pc_align
    

    Parameters
    ----------
    ascii_dtm : str
                path to the input ASCII DTM from Socet Set

    outname : str
              path to the output CSV

    """
    
    d = np.genfromtxt(ascii_dtm, skip_header=14, dtype='unicode')
    ref_df = pd.DataFrame(d, columns=["long","lat","z"])
    ref_df = ref_df.apply(pd.to_numeric)

    ## Extract lat/long/z and write out CSV. Note swapped lat/long columns
    ref_df.to_csv(path_or_buf=outname, header=False, index=False, columns=['lat','long','z'])
    
    return
    
