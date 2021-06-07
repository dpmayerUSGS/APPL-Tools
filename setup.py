from setuptools import setup, find_packages

setup(
    name = 'APPL_Tools',
    version = '1.0.0',
    description = 'Tools to support USGS Astrogeology Planetary Photogrammetry Lab workflows',
    url = 'https://github.com/USGS-Astrogeology/APPL-Tools',
    license = 'Public Domain',
    packages = find_packages(exclude=['testdata', 'graveyard']),
    scripts = ['Workflow_Scripts/hidata4gxp.py','Workflow_Scripts/hi4socet.py','Workflow_Scripts/hinoproj.py'],
    project_urls = {'Source': 'https://github.com/USGS-Astrogeology/APPL-Tools'},
)
