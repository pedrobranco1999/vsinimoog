import numpy as np
import pandas as pd
from astropy.io import fits
import os

PATH_TO_SAVE='/Spectra/'

"""
You can run this program for a single file and can be adapted to run for a list of spectrums.
You just need to create a csv file with the names of the spectrums and the rv values for each one.
Make sure that you save the csv file in this folder.
"""


def treat_rv(name_file,rv):
    
    """
    This function does the correction of the spectrum in radial velocity.
    Parameters:
    -name_file: The name of the file to correct the spectrum.
    -rv: Value of the radial velocity of the specrtum.
    """
 
    c=299792.458 ### light velocity
    
    File_op=fits.open(name_file)
    Data=File_op[0].data
    Header=File_op[0].header

    nome0=os.path.basename(name_file.split(".fits")[0])

    File_op.close()
    wave_start = Header['CRVAL1']
    wave_delta = Header['CDELT1']
    wave = np.arange(Data.size) * wave_delta + wave_start

    wave_corr=wave/(1+rv/c)

    wave_int=np.arange(wave_corr[0],wave_corr[-1],wave_delta)

    Flux_int=np.interp(wave_int,wave_corr,Data)

    Header["CDELT1"]=wave_delta
    Header["CRVAL1"]=wave_int[0]
    Header["COMMENT"]= "Corrigido na velocidade radial."
    Header["RV"] = rv
    New_name=nome0 + "_rv.fits"

    fits.writeto(PATH_TO_SAVE + New_name,Flux_int,Header,overwrite=True)
