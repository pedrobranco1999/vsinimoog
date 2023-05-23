import numpy as np
import pandas as pd
from astropy.io import fits
import os

def treat_rv(name_file,rv,folder):
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

    fits.writeto(folder + New_name,Flux_int,Header,overwrite=True)

#Stars=pd.read_csv("stars_information_others_spec.csv")

#List_fit_unr=list(Stars["fits_name_unresolved"])
#List_rv=list(Stars["rv"])

if False:
    for i in range(len(List_fit_unr)):
        treat_rv(List_fit_unr[i],List_rv[i],"/home/pedro/OneDrive/Documentos/codes/Espetros/Other_spec_treat/")

def treat_rv_one_file(name_file,rv,folder):
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
    print(2)
    #fits.writeto(folder + New_name,Flux_int,Header,overwrite=True)
    fits.writeto("KPS-1_SOPHIE_HE_2020_s_rv.fits",Flux_int,Header,overwrite=True)


#name1="/home/pedro/OneDrive/Documentos/codes/Espetros/Other_spec_treat/Kepler-39_SOPHIE_HE_2020.fits"
treat_rv_one_file('KPS-1_SOPHIE_HE_2020_s.fits',2.3,"/home/pedro/OneDrive/Documentos/codes/Espetros/")