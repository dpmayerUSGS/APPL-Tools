from os import path

# Root directory of the APPL Reference Data
root = '/archive/projects/SOCET_GXP/REFERENCE_DATA'

# MOLA Gridded Product 
mola_delta_radius_iau = path.join(root, 'MOLA_GRID/mola_256ppd_latlon_88lat_DeltaRadiusIAUSphere.tif')

# File containing list of fully-qualified paths to MOLA PEDR files
# Due to limits in "pedr2tab", the full path to pedr_list must be <= 64 characters long
#  and each line within the file (the paths to the PEDRs themselves) must be <=64 characters long
pedr_list = path.join(root,'MOLA_PEDR/pedr.lis')
