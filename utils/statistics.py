"""Statistics & Functions"""

from functools import partial

import numpy as np
from scipy.optimize import curve_fit, minimize
from scipy.stats import chi2, linregress

from utils.logger import logger


def func_linear(x, a, b):
    """Linear function"""
    return a * x + b


def lorentzian(x, pos, width, height, offset):
    """Lorentzian function for transmission spectrum curve fitting"""
    return (height / ((((x - pos) / (width / 2)) ** 2) + 1)) + offset


def chi_squared(x, y, params):
    """Chi squared calculation for affinity model"""
    return sum((x - y) ** 2) / (len(x) - params)


def p_value(obs, fit, params):
    """Calculate p value for confidence"""
    stats_chi_sq = sum(((fit - obs) ** 2) / fit)
    p = 1 - chi2.cdf(stats_chi_sq, (len(obs) - params))
    return p


def r_squared(y_data, fitted_data):
    """R^2 calculation for linear model"""
    try:
        return linregress(y_data, fitted_data).rvalue ** 2
    except Exception as e:
        logger.debug(f"linear regression error {e}")
        return np.nan


def func_affinity_fit(c_list, f):
    """Calculate fitted value from the concentration list
    :param c_list:
    :param f: List of [Rmax, KD]
    :return:
    """
    return np.array([x * f[0] / (x + f[1]) for x in c_list])


def affinity_est_func(c_list, s_list, params, f):
    """Estimation function to evaluate the result
    :param f: List of [Rmax, KD]
    :param c_list: concentration list
    :param s_list: shift list
    :param params: number of fitted parameters
    :return:
    """
    return chi_squared(func_affinity_fit(c_list, f), s_list, params)


def optimize_by_affinity(c_list, s_list):
    """Perform optimization for the KD Wizard
    :param c_list: Concentration values list
    :param s_list: Shift values list
    :return:
    """
    params = 2
    init_params = np.array([max(s_list), max(c_list) / 2])  # Rmax, KD
    res = minimize(
        fun=partial(affinity_est_func, c_list, s_list, params),
        x0=init_params,
        method="slsqp",
        options={"ftol": 1e-24, "disp": True},
    )
    fitted = func_affinity_fit(c_list, res.x).tolist()
    chi_sq = chi_squared(np.array(s_list), np.array(fitted), params)
    result = {
        "Rmax": res.x[0],
        "KD": res.x[1],
        "offset": 0,
        "fitted": fitted,
        "sd": [s - fitted[i] for i, s in enumerate(s_list)],
        "chi_sq": chi_sq,
        "p_val": p_value(np.array(s_list), np.array(fitted), params),
    }
    logger.debug(f"Affinity result - {result}")
    return result


def optimize_by_linear(xdata, ydata):
    (a, b), _ = curve_fit(f=func_linear, xdata=xdata, ydata=ydata)
    fitted = [a * c + b for c in xdata]
    result = {
        "a": a,
        "b": b,
        "fitted": fitted,
        "sd": [s - fitted[i] for i, s in enumerate(ydata)],
        "r_sq": r_squared(ydata, fitted),
    }
    logger.debug(
        f"Linear result: a = {result['a']}, b = {result['b']}, Rsq = {result['r_sq']}"
    )
    return result


def func_assoc(data, k):
    """:param data: [x_data, c, kd]
    :param k: [ka, rmax]
    """
    return np.array(
        [
            (k[0] * data[1] * k[1])
            * (1 - np.exp(-1 * ((k[0] * data[1]) + data[2]) * t))
            / ((k[0] * data[1]) + data[2])
            for t in data[0]
        ]
    )


def assoc_est_func(x_data, y_data, c, kd, params, f):
    """Estimation function to evaluate the result
    :param f: [ka, rmax]
    :param c: concentration
    :param kd: kd value
    :param x_data: time data
    :param y_data: shift data
    :param params: number of fitted parameters
    :return:
    """
    return chi_squared(func_assoc([x_data, c, kd], f), np.array(y_data), params)


def optimize_assoc(xdata, ydata, c, kd, ka0, rmax0):
    params = 2
    init_params = np.array([ka0, rmax0])
    opt_val = minimize(
        fun=partial(assoc_est_func, xdata, ydata, c, kd, params),
        x0=init_params,
        method="slsqp",
        options={"ftol": 1e-24, "disp": True},
    )
    return {"ka": opt_val.x[0], "rmax": opt_val.x[1]}


def func_rmax(data, r):
    """:param data: [c_data, kd]
    :param r: [rmax]
    """
    # Vectorized operation (5-10× faster than list comprehension)
    return (data[0] * r[0]) / (data[0] + data[1])


def rmax_est_func(c_data, shift_data, kd, params, f):
    """Estimation function to evaluate the result
    :param f: [rmax]
    :param c_data: concentration
    :param kd: kd value
    :param shift_data: equilibrium shift
    :param params: number of fitted parameters
    :return:
    """
    return chi_squared(func_rmax([c_data, kd], f), np.array(shift_data), params)


def optimize_rmax(c_data, shift_data, kd, rmax0):
    params = 1
    init_params = np.array([rmax0])
    opt_val = minimize(
        fun=partial(rmax_est_func, c_data, shift_data, kd, params),
        x0=init_params,
        method="slsqp",
        options={"ftol": 1e-8, "disp": True},
    )
    return {"rmax": opt_val.x[0]}
