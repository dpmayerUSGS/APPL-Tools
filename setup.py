from setuptools import setup, find_packages

setup(
    name = 'APPL_Tools',
    version = '1.0.0',
    description = 'Tools to support USGS Astrogeology Planetary Photogrammetry Lab workflows',
    url = 'https://github.com/USGS-Astrogeology/APPL-Tools',
    license = 'Public Domain',
    packages = find_packages(exclude=['testdata', 'graveyard']),
    scripts = ['Workflow_Scripts/ode_get_laser_alt.py','Workflow_Scripts/ode_csv2shapefile.py','Workflow_Scripts/hidata4gxp.py','Workflow_Scripts/hi4socet.py','Workflow_Scripts/hinoproj.py','SurfaceFit/surface_fit_pc_align.py','SurfaceFit/gpf_transform.py'],
    project_urls = {'Source': 'https://github.com/USGS-Astrogeology/APPL-Tools'},
)
