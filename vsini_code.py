# adapted from vsini_mpfit_stars from Ana Rita Silva and Vardan
# using vmac from formula and vrot from mpfit

from multiprocessing.pool import RUN
from ssl import get_server_certificate
import time
import os
import numpy as np
from astropy.io import fits
from scipy.interpolate import interp1d
import pandas as pd
import sys
sys.path.insert(0, os.path.dirname(repr(__file__).replace("'",""))+'mpfit/')
from mpfit import mpfit
from matplotlib import pyplot as plt
from csv import writer
from scipy.interpolate import interpn

RUN_PATH      = 'running_dir/'
#MOOG_PATH    = ""  # if you have MOOGSILENT in your path use this.
#MODELS_PATH  = ""
MOOG_PATH     = "/home/pedro/OneDrive/Documentos/codes/MOOG2019/./"  # otherwise write your full path to MOOGSILENT here
MODELS_PATH   = "/home/pedro/OneDrive/Documentos/codes/interpol_models/./"
LINELIST_PATH = 'linelist/'
SPECTRA_PATH = 'Spectra/'

def norm(obs_array_complete):
    """
    Function to normalise a given interval of data points (average flux of continuum).
    :param obs_array_complete: list of floats of data points (e.g. flux)
    :return: m, float, mean value of data points
    """
    obs_array_complete = list(obs_array_complete)
    obs_array = obs_array_complete.copy()
    m = np.mean(obs_array_complete)
    sigma = np.std(obs_array_complete)

    # define maximum iterations as desired
    max_it=15
    it = 0
    while it < max_it:
        for data_value in obs_array:
            if data_value < m-sigma or data_value > m+2*sigma:
                obs_array.remove(data_value)
            m = np.mean(obs_array)
            sigma = np.std(obs_array)
        it = it + 1

    return m

def moog_fe(star, p, vmac, lambda_i, lambda_f, ldc, CDELT1, instr_broad):
    """
    This function outputs a parameter file with the given details, outputs a text file and calls MOOGSILENT to read
    these files. In turn, MOOGSILENT will output an ascii file of a synthetic spectrum for the given star properties.
    The function then reads the data/wavelength in the ascii file.
    :param star: string, star
    :param p: list of floats, starting values of parameters (in this case, only vrot)
    :param vmac: float, macroturbulence
    :param lambda_i: float, starting wavelength of synthesis
    :param lambda_f: float, ending wavelength of synthesis
    :param ldc: float, limb darkening coefficient
    :param CDELT1: float, delta lambda in the observed spectrum
    :param instr_broad: float, instrumental broadening
    :return: .par file, .txt file, runs them through MOOGSILENT and returns a message of completion
    """

    print (star, p, vmac, lambda_i, lambda_f, ldc, CDELT1, instr_broad)

    with open(RUN_PATH+'synth_fe.par', 'w') as par:
        par.write('synth \n')
        par.write('model_in       \'' + star + '.atm\' \n')
        par.write('summary_out    \'out1\' \n')
        par.write('smoothed_out   \'synth_fe.asc\' \n')
        par.write('standard_out   \'out2\' \n')
        par.write('lines_in       \'../linelist/iron_vrot_moog.list\' \n')
        par.write('abundances     1    1\n')
        par.write('        26     0.00 \n')
        par.write('plot           1 \n')
        par.write('synlimits \n')
        par.write(str(lambda_i) + '  ' + str(lambda_f) + '   ' + str(round(CDELT1, 3)) + '  1.0 \n')
        par.write('plotpars       1 \n')
        par.write(str(lambda_i) + '   ' + str(lambda_f) + '  0.80   1.05 \n')
        par.write('0.0   0.0   0.0   1.0  \n')
        par.write('r  ' + str(round(instr_broad, 3)) + '  ' + str(round(p[0], 3)) + '  ' + str(round(ldc, 3)) + '  ' + str(round(vmac, 3)) + '  0.0 \n')
        par.write('damping        0 \n')
        par.write('atmosphere     1 \n')
        par.write('molecules      2 \n')
        par.write('trudamp        1 \n')
        par.write('lines          1 \n')
        par.write('strong         0 \n')
        par.write('flux/int       0 \n')
        par.write('units          0 \n')
        par.write('opacit         0 \n')
        par.write('obspectrum     0 \n')

    with open(RUN_PATH+'synth_fe.txt', 'w') as txt:
        txt.write('synth_fe.par \n')
        txt.write('f \n')
        #txt.write(star + '_fe.ps \n')
        txt.write('q \n')

    os.system('rm '+RUN_PATH+'batch.par')
    os.system('cd '+RUN_PATH+' && '+MOOG_PATH+'MOOGSILENT < synth_fe.txt')

    return 'Finished MOOG synthesis for ' + star + ' in range ' + str(lambda_i) + ' to ' + str(lambda_f) + '.'

def minimize_synth(p, star, vmac, fe_intervals, obs_lambda, obs_flux, ldc, CDELT1, instr_broad, **kwargs):
    """
    Function to minimize a model to observational data.
    :param p: list, initial values of parameters
    :param star: string, star name
    :param vmac: float, value of macroturbulence of star
    :param fe_lines_intervals: intervals where iron lines are present
    :param fe_intervals_lambda: fe intervals that contain the start and end point of the synthesis
    :param obs_flux: list of observational flux points
    :param ldc: float, limb darkening coefficient
    :param CDELT1: float, delta lambda in the observed spectrum
    :param kwargs
    :return: best values of parameters
    """


    def myfunct(p, star=None, vmac=None, fe_intervals=None, obs_lambda=None,
                obs_flux=None, flux_err=0.01, **kwargs):
        """
        User supllied function that contains the model to be tested. Calculates the synthetic points at the same
        wavelength of the observational points (this means inside the iron lines regions).
        Returns an integer as status of the calculation and an array of deviates between the data points and the model
        points, normalized by the error in the observation (here, an arbitrary value is given as HARPS did not provide
        errors).
        :param p: list, initial values of parameters
        :param star: string, star name
        :param vmac: float, macroturbulence of star
        :param fe_lines_intervals: intervals where iron lines are present
        :param obs_flux: list of observational flux points
        :param flux_err: float, error in observational flux points (set to 0.01 here)
        :param kwargs
        :return: integer (status of operations), array of deviates
        """

        #print round(p[0], 3)

        #lambda_i_values = [round(fe_intervals_lambda[0][0], 3), round(fe_intervals_lambda[0][0], 3) +2.01]
        #lambda_f_values = [round(fe_intervals_lambda[0][0], 3) + 2.00, round(fe_intervals_lambda[-1][1], 3)]

        gap = obs_lambda[-1] - obs_lambda[0]
        if gap <= 450:
            lambda_i_values = [round(obs_lambda[0], 3)]
            lambda_f_values = [round(obs_lambda[-1], 3)]
        elif gap > 450 and gap <= 900:
            lambda_i_values = [round(obs_lambda[0], 3), round(obs_lambda[int(len(obs_lambda)/2)], 3)]
            lambda_f_values = [round(obs_lambda[int(len(obs_lambda)/2)-1], 3), round(obs_lambda[-1], 3)]
        elif gap > 900:
            lambda_i_values = [round(obs_lambda[0], 3), round(obs_lambda[int(len(obs_lambda)/3)], 3), round(obs_lambda[int(len(obs_lambda)/3*2)], 3)]
            lambda_f_values = [round(obs_lambda[int(len(obs_lambda)/3)-1], 3), round(obs_lambda[int(len(obs_lambda)/3*2)-1], 3), round(obs_lambda[-1], 3)]

        synth_data = []  # all flux values from model
        synth_lambda = []  # all wavelength points from model

        for lambda_i, lambda_f in zip(lambda_i_values, lambda_f_values):
            moog_fe(star, p, vmac, lambda_i, lambda_f, ldc, CDELT1, instr_broad)
            with open(RUN_PATH+'synth_fe.asc') as asc:
                for x in asc:
                    if x[0] == ' ':
                        entry = x.rstrip().split()
                        synth_lambda.append(float(entry[0]))
                        synth_data.append(float(entry[1]))

        synth_data_fe = []
        synth_lambda_fe = []

        fe_intervals_list = [row for row in fe_intervals[['ll_li', 'll_lf','ll_si','ll_sf']].to_numpy()]

        for i,(ll_li, ll_lf, ll_si, ll_sf) in enumerate(fe_intervals_list):
            select_sll = np.where((synth_lambda >= ll_si) & (synth_lambda <= ll_sf))[0]
            synth_data_fe.extend(list(np.array(synth_data)[select_sll]))
            synth_lambda_fe.extend(list(np.array(synth_lambda)[select_sll]))

        obs_flux = np.array(obs_flux)
        synth_data_fe = np.array(synth_data_fe)

        err = np.zeros(len(obs_flux)) + flux_err
        status = 0

        return [status, (obs_flux - synth_data_fe)/err]

    def convergence_info(res, parinfo, dof):
        """
        Function that returns the best parameter values and errors.
        :param res: output object resultant from mpfit function
        :param parinfo: list of dictionaries of parameter information
        :param dof: float, degrees of freedom
        :return: best parameter values and errors
        """

        if res.status == -16:
            print('status = {0:4}: A parameter or function value has become infinite or an undefined number.'
                    .format(res.status))
        elif -15 <= res.status <= -1:
            print('status = {0:4}: MYFUNCT or iterfunct functions return to terminate the fitting process.'
                    .format(res.status))
        elif res.status == 0:
            print('status = {0:4}: Improper input parameters.'.format(res.status))
        elif res.status == 1:
            print('status = {0:4}: Both actual and predicted relative reductions in the sum of squares are at most ftol'
                    '.'.format(res.status))
        elif res.status == 2:
            print('status = {0:4}: Relative error between two consecutive iterates is at most xtol.'.format(res.status))
        elif res.status == 3:
            print('status = {0:4}: Conditions for status = 1 and status = 2 both hold.'.format(res.status))
        elif res.status == 4:
            print('status = {0:4}: The cosine of the angle between fvec and any column of the jacobian is at most gtol '
                    'in absolute value.'.format(res.status))
        elif res.status == 5:
            print('status = {0:4}: The maximum number of iterations has been reached.'.format(res.status))
        elif res.status == 6:
            print('status = {0:4}: ftol is too small'.format(res.status))
        elif res.status == 7:
            print('status = {0:4}: xtol is too small.'.format(res.status))
        elif res.status == 8:
            print('status = {0:4}: gtol is too small'.format(res.status))

        # res.niter = number of iterations
        # res.fnorm = summed square residuals
        chi_reduced = round((res.fnorm/dof), 4)
        vrot = round(float(res.params[0]), 3)
        vrot_err = round(float(res.perror[0]), 3)
        vrot_parameters = [vrot, vrot_err, res.niter, round(float(res.fnorm), 3), chi_reduced, res.status]

        print (star, ('%s: %s +- %s' % (parinfo[0]['parname'], vrot, vrot_err)))

        return vrot_parameters

    # define parameters for minimization
#    vrot_info = {'parname': 'vrot', 'value': 15, 'fixed': 0, 'limited': [1, 1], 'limits': [1, 20], 'mpside': 2,
#                    'step': 0.001}
    vrot_info = {'parname': 'vrot', 'value': 5, 'fixed': 0, 'limited': [1, 1], 'limits': [0.1, 60], 'mpside': 2,
                    'step': 0.001}
    parinfo = [vrot_info]

    fa = {'star': star, 'vmac': vmac, 'fe_intervals': fe_intervals, 'obs_lambda':
            obs_lambda, 'obs_flux': obs_flux}
    # call for minimization

    m = mpfit(myfunct, parinfo=parinfo, functkw=fa, ftol=1e-5, xtol=1e-5, gtol=1e-5, maxiter=20)

    dof = len(obs_flux) - len(m.params)
    parameters = convergence_info(m, parinfo, dof)

    return parameters

def creating_final_synth_spectra(vsini, star, spectrum, teff, feh, vtur, logg, fe_intervals, ldc, instr_broad):
    obs_lambda, obs_flux, synth_data_fe = create_obs_synth_spec(star, spectrum, teff, feh, vtur, logg, ldc, instr_broad, fe_intervals, vsini)
    flux_ratio = (obs_flux / synth_data_fe)
    flux_diff = (obs_flux - synth_data_fe)
    synth_normalized_spectra = pd.DataFrame(data=np.column_stack((obs_lambda, synth_data_fe, flux_diff, flux_ratio)),columns=['wl','flux', 'flux_diff', 'flux_ratio'])
    synth_normalized_spectra.to_csv('running_dir/%s_synth_normalized_spectra.rdb' % star, index = False, sep = '\t')


def get_spectra(fitsfile):
    img_data, img_header = fits.getdata(fitsfile, header=True)
    cdelta1 = img_header['CDELT1']
    crval1  = img_header['CRVAL1']
    npoints = img_header['NAXIS1']
    ll = np.arange(0,npoints)*cdelta1+crval1
    return ll, img_data, cdelta1

def get_intervals_normalized_spectra(ll, flux, fe_intervals):
    obs_data_norm = []
    obs_lambda = []
    fe_intervals_list = [row for row in fe_intervals[['ll_li', 'll_lf','ll_si','ll_sf']].to_numpy()]
    for i,(ll_li, ll_lf, ll_si, ll_sf) in enumerate(fe_intervals_list):
        # get data from large intervals to do normalisation in each region
        select_ll = np.where((ll >= ll_li) & (ll <= ll_lf))[0]
        obs_data_one_large_interval = flux[select_ll]

        # m : mean value of larger interval to divide the smaller interval by
        m = norm(obs_data_one_large_interval)

        # get data from smaller intervals and normalising it
        select_sll = np.where((ll >= ll_si) & (ll <= ll_sf))[0]
        obs_data_one_small_interval = flux[select_sll]/m
        obs_lambda_one_small_interval = ll[select_sll]

        #print 'obs_data_one_small_interval',  obs_data_one_small_interval
        #obs_data_norm.append(obs_data_one_small_interval)
        #obs_lambda.append(obs_lambda_one_small_interval)
        obs_data_norm.extend(list(obs_data_one_small_interval))
        obs_lambda.extend(list(obs_lambda_one_small_interval))

    # single list with data from all fe regions
    
    #print ('finished')
    #print 'obs_data', obs_data_norm
    #obs_data_norm_flat = [float(value) for sublist in obs_data_norm for value in sublist]
    #print 'obs_data_norm', obs_data_norm
    # single list with wavelength points from all fe regions
    #obs_lambda_flat = [float(value) for sublist in obs_lambda for value in sublist]
    #print ('obs_data all together', obs_data_norm_flat)
    #print "obs_lambda", np.array(obs_lambda)
    #return obs_lambda_flat, obs_data_norm_flat
    return obs_lambda,obs_data_norm


def create_atm_model(teff, log_g, feh, vtur, star):
    owd = os.getcwd()
    os.chdir(RUN_PATH)
    ## Modify to use functions in run_programs
    os.system('echo %s %s %s | ' % (teff, log_g, feh) + MODELS_PATH + 'intermod.e' )
    os.system('echo %s | ' % vtur + MODELS_PATH + 'transform.e' )
    os.system('mv out.atm %s.atm' %star)
    os.system('rm mod* for*')
    os.chdir(owd)


def get_vmac(teff, log_g):
    if teff <= 5000.0:
        vmac_funct = 2.0
    elif 6500.0 > teff > 5000.0:
        vmac_funct = 3.21 + 2.33e-3*(teff-5777) + 2.00e-6*(teff-5777)**2-2.00*(log_g-4.44)
        #macroturbulence calibration by Doyle et al. 2014
    elif teff >= 6500.0:
        vmac_funct = 5.5
        # code was run with slight changes to exception stars: HD82342, HD55, HD108564, HD145417, HD134440, HD23249,
        # HD40105, HD92588, HD31128, HD52449
    return vmac_funct


def get_vsini(star, spectrum, teff, feh, vtur, logg, ldc, instr_broad, fe_intervals):
    create_atm_model(teff, logg, feh, vtur, star)
    vmac = round(float(get_vmac(teff, logg)), 3)

    # read observational spectra
    obs_lambda_full_spectrum, obs_data_full_spectrum, delta_lambda =  get_spectra(spectrum)
    interp_function = interp1d(obs_lambda_full_spectrum, obs_data_full_spectrum)
    # create wavelength array equal to that of the synthetic models
    # starts at the first value of the first fe region and ends at the end value of the last region
    obs_lambda_interp = np.arange(np.min(fe_intervals['ll_li']),np.max(fe_intervals['ll_lf'])+round(float(delta_lambda), 3), round(float(delta_lambda), 3))
    obs_lambda_interp = np.round(obs_lambda_interp,3)
    # Why do we need to interpolate??? To get round values for the synthesis calculation

    obs_data_interp = interp_function(obs_lambda_interp)
    #print 'obs lambda interpolated', obs_lambda_interp
    #print 'obs data interpolated' , obs_data_interp

    # get wavelength points and flux data for Fe lines in interpolated rounded wavelenghts

    obs_lambda_flat, obs_data_norm_flat = get_intervals_normalized_spectra(obs_lambda_interp, obs_data_interp, fe_intervals)

    obs_normalized_spectra = pd.DataFrame(data=np.column_stack((obs_lambda_flat,obs_data_norm_flat)),columns=['wl','flux'])
    obs_normalized_spectra.to_csv(RUN_PATH+'/%s_obs_normalized_spectra.rdb' % star, index = False, sep = '\t')

    par_list = [0.5]

    final_vrot  = minimize_synth(p=par_list, star=star, vmac=vmac, fe_intervals=fe_intervals,
                                obs_lambda=obs_lambda_flat, obs_flux=obs_data_norm_flat, ldc = ldc, CDELT1 = delta_lambda, instr_broad = instr_broad)

    vrot = final_vrot[0]
    vrot_err = final_vrot[1]
    status = final_vrot[5]

    #creating_final_synth_spectra(vsini = final_vrot, star = star, vmac = vmac, fe_intervals=fe_intervals, obs_lambda=obs_lambda_flat, obs_flux=obs_data_norm_flat, ldc = ldc, CDELT1 = delta_lambda, instr_broad = instr_broad, flux_err=1)

    print ('results', star, teff, logg, feh, spectrum, final_vrot)

    #stars_par.write('{:10} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10} \n'.format(star, teff, log_g, feh,
    #                                                                                    final_vrot[0], final_vrot[1],
    #                                                                                    round(vmac_funct,3), round(ldc,3), instr_broad))

    return vrot, vrot_err, vmac, status

def get_vsini_error(star, spectrum, teff, eteff, feh, efeh, vtur, logg, ldc, instr_broad, fe_intervals):
    #parameters = ['teff', 'feh']
    vrot, vrot_err, vmac, status = get_vsini(star, spectrum, teff, feh, vtur, logg, ldc, instr_broad, fe_intervals)
    vrot_tm, vrot_err_tm, vmac_tm, status_tm = get_vsini(star, spectrum, teff-eteff, feh, vtur, logg, ldc, instr_broad, fe_intervals)
    vrot_tp, vrot_err_tp, vmac_tp, status_tp = get_vsini(star, spectrum, teff+eteff, feh, vtur, logg, ldc, instr_broad, fe_intervals)
    vrot_fm, vrot_err_fm, vmac_fm, status_fm = get_vsini(star, spectrum, teff, feh-efeh, vtur, logg, ldc, instr_broad, fe_intervals)
    vrot_fp, vrot_err_fp, vmac_fp, status_fp = get_vsini(star, spectrum, teff, feh+efeh, vtur, logg, ldc, instr_broad, fe_intervals)

    vsini_final_err = np.sqrt( np.abs( (vrot_tm - vrot) - (vrot_tp - vrot) )**2. + np.abs( (vrot_fm - vrot) - (vrot_fp - vrot) )**2. + vrot_err**2. )


    print(vrot, vrot_err, vmac, status)
    print(vrot_tm, vrot_err_tm, vmac_tm, status_tm)
    print(vrot_tp, vrot_err_tp, vmac_tp, status_tp)
    print(vrot_fm, vrot_err_fm, vmac_fm, status_fm)
    print(vrot_fp, vrot_err_fp, vmac_fp, status_fp)
    return vrot, vrot_err, vmac, status, vsini_final_err


def create_obs_synth_spec(star, spectrum, teff, feh, vtur, logg, ldc, instr_broad, fe_intervals, vrot_test):
    # read observational spectra
    obs_lambda_full_spectrum, obs_data_full_spectrum, delta_lambda =  get_spectra(spectrum)
    interp_function = interp1d(obs_lambda_full_spectrum, obs_data_full_spectrum)
    obs_lambda_interp = np.arange(np.min(fe_intervals['ll_li']),np.max(fe_intervals['ll_lf'])+round(float(delta_lambda), 3), round(float(delta_lambda), 3))
    obs_lambda_interp = np.round(obs_lambda_interp,3)
    obs_data_interp = interp_function(obs_lambda_interp)
    obs_lambda_flat, obs_data_norm_flat = get_intervals_normalized_spectra(obs_lambda_interp, obs_data_interp, fe_intervals)
    obs_normalized_spectra = pd.DataFrame(data=np.column_stack((obs_lambda_flat,obs_data_norm_flat)),columns=['wl','flux'])


    create_atm_model(teff, logg, feh, vtur, star)
    vmac = round(float(get_vmac(teff, logg)), 3)
    print(teff, logg, feh, vtur, vmac)

    obs_lambda = np.array(obs_normalized_spectra['wl'])
    CDELT1 = delta_lambda
    p = [vrot_test]

    
    gap = obs_lambda[-1] - obs_lambda[0]
    if gap <= 450:
        lambda_i_values = [round(obs_lambda[0], 3)]
        lambda_f_values = [round(obs_lambda[-1], 3)]
    elif gap > 450 and gap <= 900:
        lambda_i_values = [round(obs_lambda[0], 3), round(obs_lambda[int(len(obs_lambda)/2)], 3)]
        lambda_f_values = [round(obs_lambda[int(len(obs_lambda)/2)-1], 3), round(obs_lambda[-1], 3)]
    elif gap > 900:
        lambda_i_values = [round(obs_lambda[0], 3), round(obs_lambda[int(len(obs_lambda)/3)], 3), round(obs_lambda[int(len(obs_lambda)/3*2)], 3)]
        lambda_f_values = [round(obs_lambda[int(len(obs_lambda)/3)-1], 3), round(obs_lambda[int(len(obs_lambda)/3*2)-1], 3), round(obs_lambda[-1], 3)]

    synth_data = []  # all flux values from model
    synth_lambda = []  # all wavelength points from model

    for lambda_i, lambda_f in zip(lambda_i_values, lambda_f_values):
        moog_fe(star, p, vmac, lambda_i, lambda_f, ldc, CDELT1, instr_broad)
        with open(RUN_PATH+'synth_fe.asc') as asc:
            for x in asc:
                if x[0] == ' ':
                    entry = x.rstrip().split()
                    synth_lambda.append(float(entry[0]))
                    synth_data.append(float(entry[1]))

    synth_data_fe = []
    synth_lambda_fe = []

    fe_intervals_list = [row for row in fe_intervals[['ll_li', 'll_lf','ll_si','ll_sf']].to_numpy()]

    for i,(ll_li, ll_lf, ll_si, ll_sf) in enumerate(fe_intervals_list):
        select_sll = np.where((synth_lambda >= ll_si) & (synth_lambda <= ll_sf))[0]
        synth_data_fe.extend(list(np.array(synth_data)[select_sll]))
        synth_lambda_fe.extend(list(np.array(synth_lambda)[select_sll]))

    obs_flux = np.array(obs_normalized_spectra['flux'])
    synth_data_fe = np.array(synth_data_fe)

    return obs_lambda, obs_flux, synth_data_fe


def manual_test(star, spectrum, teff, feh, vtur, logg, ldc, instr_broad, fe_intervals, vrot_test):
    obs_lambda, obs_flux, synth_data_fe = create_obs_synth_spec(star, spectrum, teff, feh, vtur, logg, ldc, instr_broad, fe_intervals, vrot_test)
    plt.plot(obs_lambda, obs_flux)
    plt.plot(obs_lambda, synth_data_fe)
    plt.show()

#### In these few lines bellow the goal is to determine the coefficient of limb darkening of the star

Tabela1=pd.read_csv("limb_values.csv") ### These values were calculated with Exoctk
Temperature=np.arange(3500,7000,100)
Logg=np.arange(3.0,5.0,0.1)
FeH=np.arange(-0.5,0.6,0.1)
Variables=(Temperature,Logg,FeH)
Values_limbo=np.array(Tabela1["Limbo"])

VL=np.zeros((len(Temperature),len(Logg),len(FeH)))
zz=0

for i in range(len(Temperature)):
    for j in range(len(Logg)):
        for k in range(len(FeH)):
            VL[i][j,k]=Values_limbo[zz]
            zz+=1

def interpolation_function(T,log,feh):

    """
    This function determines the limb darkening coefficient for some parameters of the star
    The range of the values accepted are:
    T:[3500,7000]
    log:[3.0,5.0]
    FeH:[-0.5,0.5]
    Parameters:
    T: Temperature of the star
    log: logg on the surface of the star
    feh: matallicity of the star
    """

    return interpn(Variables, VL,np.array([T,log,feh]))[0]




### Main program:
def main():
   
    directory="stars_information.csv"
    Table=pd.read_csv(directory)

    star_names=list(Table["star_name"])
    fits_directory=np.array(list(Table["fits_name"]))

    N=len(star_names)  #number of data to analyse


    print("Running Dir:", RUN_PATH)

    start_time = time.time()
    fe_intervals = pd.read_csv(LINELIST_PATH+'vsini_intervals.list', sep='\t')
    
    for i in range(N):
        star = star_names[i]
        spect=list(Table[Table["star_name"]==star]["spectrograph"])[0]
        teff = float(Table[Table["star_name"]==star]["Teff"])
        eteff = float(Table[Table["star_name"]==star]["eTeff"])
        logg = float(Table[Table["star_name"]==star]["logg"])
        feh  = float(Table[Table["star_name"]==star]["feh"])
        efeh = float(Table[Table["star_name"]==star]["efeh"])
        vtur = float(Table[Table["star_name"]==star]["vtur"])
        ldc  = float(interpolation_function(teff,logg,feh))   #https://exoctk.stsci.edu/limb_darkening
        instr_broad = float(Table[Table["star_name"]==star]["instr_broad"])
    #spectrum = "/home/pedro/OneDrive/Documentos/codes/Espetros/" + directory
    
        print(spect,SPECTRA_PATH+fits_directory[i],star,teff,eteff,logg,feh,efeh,vtur,ldc,instr_broad)    #manual_test(star, fits_directory[i], teff, feh, vtur, logg, ldc, instr_broad, fe_intervals,2.87)    #return#    print (star, teff, logg, feh, vtur, ldc, instr_broad, fits_directory[i])    vrot, vrot_err, vmac, status = get_vsini(star, fits_directory[i], teff, feh, vtur, logg, ldc, instr_broad, fe_intervals)#    creating_final_synth_spectra(vrot, star, fits_directory[i], teff, feh, vtur, logg, fe_intervals, ldc, instr_broad)#With Error propagation    #vrot, vrot_err, vmac, status, vsini_final_err = get_vsini_error(star, fits_directory[i], teff, eteff, feh, efeh, vtur, logg, ldc, instr_broad, fe_intervals)    #creating_final_synth_spectra(vrot, star, fits_directory[i], teff, feh, vtur, logg, fe_intervals, ldc, instr_broad)    #print ('results', star, teff, logg, feh, fits_directory[i], vrot, vrot_err, vmac, status, vsini_final_err)

        #manual_test(star, SPECTRA_PATH+fits_directory[i], teff, feh, vtur, logg, ldc, instr_broad, fe_intervals,7.0)
    #return

        print (star, teff, logg, feh, vtur, ldc, instr_broad, fits_directory[i])

#    vrot, vrot_err, vmac, status = get_vsini(star, fits_directory[i], teff, feh, vtur, logg, ldc, instr_broad, fe_intervals)
#    creating_final_synth_spectra(vrot, star, fits_directory[i], teff, feh, vtur, logg, fe_intervals, ldc, instr_broad)
#    print ('results', star, teff, logg, feh, fits_directory[i], vrot, vrot_err, vmac, status)

#With Error propagation
        vrot, vrot_err, vmac, status, vsini_final_err = get_vsini_error(star,SPECTRA_PATH+ fits_directory[i], teff, eteff, feh, efeh, vtur, logg, ldc, instr_broad, fe_intervals)
        creating_final_synth_spectra(vrot, star, SPECTRA_PATH+fits_directory[i], teff, feh, vtur, logg, fe_intervals, ldc, instr_broad)
        print ('results', star, teff, logg, feh, SPECTRA_PATH+fits_directory[i], vrot, vrot_err, vmac, status, vsini_final_err)

    #saving the results in a csv file
        List=[star,instr_broad,teff,logg,feh,vrot, vrot_err, vmac, status, vsini_final_err]
    
        with open('results_simulations.csv', 'a') as f_object:
 
        # Pass this file object to csv.writer()
        # and get a writer object
    
            writer_object = writer(f_object)
 
        # Pass the list as an argument into
        # the writerow()
            writer_object.writerow(List)
 
        # Close the file object
            f_object.close()
    

if __name__ == "__main__":
    main()
