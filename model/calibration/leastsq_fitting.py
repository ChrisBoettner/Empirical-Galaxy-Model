#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  7 15:48:41 2022

@author: chris
"""

import numpy as np
from scipy.optimize import least_squares, dual_annealing, brute, minimize

from model.helper import within_bounds
from model.quantity_options import update_bounds

################ MAIN FUNCTIONS ###############################################


def lsq_fit(model, method='least_squares'):
    '''
    Calculate parameter that match observed LFs to modelled LFs using least
    squares regression and a pre-defined cost function (which is not the usual
    one! See cost_function for details).
    '''
    bounds = list(zip(*model.physics_model.at_z(model._z).bounds))
    # fit lf model to data based on pre-defined cost function
    if method == 'least_squares':
        optimization_res = least_squares(
            cost_function,
            model.physics_model.at_z(model._z).initial_guess,
            bounds=model.physics_model.at_z(model._z).bounds,
            args=(
                model,
                'res'))

    elif method == 'minimize':
        optimization_res = minimize(
            cost_function,
            x0=model.physics_model.at_z(model._z).initial_guess,
            bounds=bounds,
            args=(
                model,
            ))

    elif method == 'annealing':
        optimization_res = dual_annealing(cost_function,
                                          bounds=bounds,
                                          maxiter=1000,
                                          args=(model,))
    elif method == 'brute':
        optimization_res = brute(cost_function,
                                 ranges=bounds,
                                 Ns=100,
                                 args=(model,))
    else:
        raise NameError('method not known.')

    par = optimization_res.x
    if not optimization_res.success:
        print('Warning: Optimization did not succeed')

    par_distribution = None  # for compatibility with mcmc fit
    return(par, par_distribution)


def cost_function(params, model, out='cost', weighted=True, z=None):
    '''
    Cost function for fitting. Includes physically sensible bounds for parameter.

    Fitting is perfomed in either log space (res = log_phi_obs - log_phi_mod)
    or linear space (res = 10**log_phi_obs - 10**log_phi_mod), depending on
    quantity_options of model.

    If weighted is True, include errorbars in fit. The weights are calculated
    as the inverse of the RELATIVE uncertainties.
    '''
    if z is None:
        z = model._z
    
    log_quantity_obs = model.log_ndfs.at_z(z)[:, 0]
    log_phi_obs = model.log_ndfs.at_z(z)[:, 1]

    # check if parameter are within bounds
    bounds = update_bounds(model, params) # update first
    if not within_bounds(params, *bounds):
        return(1e+30)  # if outside of bound, return huge value to for cost func

    # calculate model ndf
    log_phi_mod = model.calculate_log_abundance(log_quantity_obs, z, params)
    if not np.all(np.isfinite(log_phi_mod)):
        return(1e+30)
    
    
    # quantity-related fitting options
    fitting_space    = model.quantity_options['fitting_space']
    relative_weights = model.quantity_options['relative_weights']
    
    # calculate residuals in log space
    if fitting_space == 'log':
        res = log_phi_obs - log_phi_mod
    elif fitting_space == 'linear':
        res = 10**log_phi_obs - 10**log_phi_mod
    else:
        raise NameError('Fitting space not known.')

    # calculate weights
    if weighted:
        weights = calculate_weights(model, relative=relative_weights)
    else:
        weights = 1

    weighted_res = res * weights

    if out == 'res':
        return(weighted_res)  # return residuals

    cost = np.sum(weighted_res**2)
    if out == 'cost':
        return(cost)  # otherwise return cost
    else:
        raise NameError('out not known.')


################ UNCERTAINTIES AND WEIGHTS ####################################
def calculate_weights(model, z=None, relative=True):
    '''
    Calculate weights for residuals based on measurement uncertainties.
    If any uncertainties are not finite (inf or nan), assign 10* largest errors
    of the remaining set to them, to be save.

    If relative is true, use relative uncertainties.

    '''
    if z is None: # if no specific redshift is given, use current temporary one
        z = model._z

    log_phi_obs = model.log_ndfs.at_z(z)[:, 1]
    log_phi_obs_uncertainties = model.log_ndfs.at_z(z)[:, 2:]

    # transform to linear space
    lower_bound = 10**(log_phi_obs - log_phi_obs_uncertainties[:, 0])
    upper_bound = 10**(log_phi_obs + log_phi_obs_uncertainties[:, 1])

    uncertainty = (upper_bound - lower_bound) / 2

    # replace nan values with large error estimate
    uncertainty[np.logical_not(np.isfinite(uncertainty))
                ] = np.nanmax(uncertainty) * 10

    if relative:
        uncertainty = uncertainty / 10**log_phi_obs

    weights = 1 / uncertainty
    return(weights)
