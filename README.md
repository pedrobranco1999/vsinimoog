# vsinimoog
Version of Sergio Sousa modified.

The code that generates the vsini result is the vsini_code.py. You need to put the parameters of the star that you want to calculate the vsini.
You need to insert the parameters in the "stars_information.csv" file and run the program. The columns are the following:
- star_name: the name of star in study
- spectrograph: the name of the spectrograph used.
- Teff: the effective temperature of the star.
- eTeff: the error of the effective temperature of the star.
- logg: the logarithmic of the gravity acceleration on the surface of the star
- -feh: the metallicity of the star.
- efeh: the error of the metallicity of the star.
- vtur: the turbulence velocity.
- instr_broad: the instrumental broadening.
- fits_name: name of the spectrum of the star. You should save the spectra on the folder named "Spectra".

The output is saved in another csv file named "results_simulations.csv". The columns of this file are the following:

- star_name: the name of star in study
- spectrograph: the name of the spectrograph used.
- instr_broad: the instrumental broadening.
- teff: the effective temperature of the star.
- logg: the logarithmic of the gravity acceleration on the surface of the star
- feh: the metallicity of the star.
- vrot: vsin simulated by the code.
- vrot_err: ask latter
- vmac: macroturbulence velocity
- status: ask latter
- vsini_final_err: uncertain of the vsini simulated by the code.

## Aditional codes:
In this repository there is a folder named "RV_for_correction" that you can correct your fit files spectrum in respect of the radial veloity.
