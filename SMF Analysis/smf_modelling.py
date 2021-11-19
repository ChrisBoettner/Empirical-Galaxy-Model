#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 18 16:03:46 2021

@author: boettner
"""
import numpy as np
from scipy.interpolate import interp1d
from pynverse import inversefunc
import leastsq_fitting
import mcmc_fitting

## MAIN FUNCTION
def fit_SMF_model(smfs, hmfs, feedback_name, fitting_method = 'least_squares',
                  mode = 'loading', m_crit=1e+11):
    '''
    Fit the modelled SMF (modelled from HMF + feedback) to the observed SMF (for
    all redshifts).
    Three feedback models: 'none', 'sn', 'both'
    Critical mass is pre-set to 1e+11
    
    Abundances (phi values) below 1e-6 are cut off because they cant be measured
    reliably.
    
    IMPORTANT   : When fitting the sn feedback model, only values up th the critical
                  mass are included.
    
    Returns:
    params       :   set of fitted parameter (A, alpha, beta)
    modelled_smf :   modelled SMF obtained from scaling HMF
    cost          :  value of cost function between modelled SMF and observational data
    '''
    
    # choose fitting method
    if fitting_method == 'least_squares':
        fit = leastsq_fitting.lsq_fit
    elif fitting_method == 'mcmc':
        def fit(smf, hmf, smf_model, z = 0): # choose saving/loading mode
            return(mcmc_fitting.mcmc_fit(smf, hmf, smf_model, mode, z))
    
    parameter = []; modelled_smf = []; cost = []
    for i in range(len(smfs)):
        smf = smfs[i][smfs[i][:,1]>1e-6] # cut unreliable values
        hmf = hmfs[i+1]                  # list starts at z=0 not 1, like smf
        
        # if just sn feedback is fitted, ignore values above high-mass knee, because 
        # they screw up the fit
        if feedback_name == 'sn':
            smf = smf[smf[:,0]<m_crit]  
        
        smf_model = smf_model_class(hmf, feedback_name, m_crit) 
        
        # fit and fit parameter
        params, mod_smf, c = fit(smf, hmf, smf_model, z=i+1) 
        parameter.append(params)
        modelled_smf.append(mod_smf)
        cost.append(c)      
    return(parameter, modelled_smf, cost)

## CREATE THE SMF MODEL
class smf_model_class():
    def __init__(self, hmf, feedback_name, m_crit):
        self.hmf_function   = interp1d(*hmf.T) # turn hmf data into evaluable function (using linear interpolation)
        self.feedback_model = feedback_model(feedback_name, m_crit) # choose feedback model function
        
    def function(self, m_star, params):
        '''
        Create SMF model function
        dn/dlogm_*(m_*) = dn/dlogm_h(m_h(m_*)) * m_*/m_h * dm_h/dm_*(m_*)
                        = dn/dlogm_h(m_h)      * m_*/m_h * 1/[dm_*/dm_h(m_h)]
        '''
        fb_function   = lambda m: self.feedback_model.function(m, *params)
        fb_derivative = self.feedback_model.derivative
        
        # using input m_* value, invert m_*(m_h) to get m_h
        m_h = inversefunc(fb_function, y_values=m_star)
        print(m_star)
        print(params)
        print(m_h)
        
        # calculate dm_h/dm_*(m_*) by using inverse rule
        # dm_h/dm_*(m_*) = 1/[dm_*/dm_h(m_h)]
        inverse_derivative = 1/fb_derivative(m_h,*params)
        
        if np.any(params<0):
            return()
        
        return(self.hmf_function(m_h) * m_star/m_h * inverse_derivative)

# DEFINE THE FEEDBACK MODELS
def feedback_model(feedback_name, m_crit):
    '''
    Return feedback model that relates SMF and HMF, including model function, 
    model name and initial guess for fitting, that related SMF and HMF. 
    The model function parameters are left free and can be obtained via fitting.
    Three models implemented:
        none    : no feedback adjustment
        sn      : supernova feedback
        both    : supernova and black hole feedback
    '''
    if feedback_name == 'none':  
        model = no_feedback(feedback_name, m_crit)
    if feedback_name == 'sn':  
        model = supernova_feedback(feedback_name, m_crit)
    if feedback_name == 'both':  
        model = supernova_blackhole_feedvack(feedback_name, m_crit)
    return(model)

class no_feedback():
    def __init__(self, feedback_name, m_crit):
        self.name          = feedback_name
        self.m_c           = m_crit
        self.initial_guess = [0.01]
    def function(self, m, A):
        # the function m_* = f(m_h)
        return(A*m)
    def derivative(self, m, A):
        # the derivative dm_*/dm_h = f(m_h)
        return(A)
    
class supernova_feedback():
    def __init__(self, feedback_name, m_crit):
        self.name          = feedback_name
        self.m_c           = m_crit
        self.initial_guess = [0.01, 1] 
    def function(self, m, A, alpha):
        # the function m_* = f(m_h)
        return( A * (m/self.m_c)**alpha *m)    
    def derivative(self, m, A, alpha):
        # the derivative dm_*/dm_h = f(m_h)
        return(A * (alpha+1) * (m/self.m_c)**alpha)

class supernova_blackhole_feedvack():
    def __init__(self, feedback_name, m_crit):
        self.name          = feedback_name
        self.m_c           = m_crit
        self.initial_guess = [0.01, 1, 1]
    def function(self, m, A, alpha, beta):
        # the function m_* = f(m_h)
        return(A * 1/((m/self.m_c)**(-alpha)+(m/self.m_c)**(beta)))        
    def derivative(self, m, A, alpha, beta):
        # the derivative dm_*/dm_h = f(m_h)
        x = (m/self.m_c)
        q = alpha+beta
        numerator   = A*x**alpha *(-(beta-1)*x**q + alpha + 1)
        denominator = (x**q +1)**2
        return(numerator/denominator)    


            
        