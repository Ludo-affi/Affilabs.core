"""Statistics & Functions."""

from functools import partial

import numpy as np
from scipy.optimize import curve_fit, minimize
from scipy.stats import chi2, linregress

from affilabs.utils.logger import logger

# Default optimization tolerance (can be adjusted for performance)
DEFAULT_FTOL = 1e-12


def func_linear(x, a, b):
    """Linear function."""
    return a * x + b


def lorentzian(x, pos, width, height, offset):
    """Lorentzian function for transmission spectrum curve fitting."""
    if abs(width) < 1e-10:
        logger.warning("Lorentzian width too small, using minimum value")
        width = 1e-10
    return (height / ((((x - pos) / (width / 2)) ** 2) + 1)) + offset


def chi_squared(x, y, params):
    """Chi squared calculation for affinity model."""
    if len(x) <= params:
        logger.warning(f"Insufficient data points ({len(x)}) for {params} parameters")
        return np.inf
    return sum((x - y) ** 2) / (len(x) - params)


def p_value(obs, fit, params):
    """Calculate p value for confidence."""
    stats_chi_sq = sum(((fit - obs) ** 2) / fit)
    return 1 - chi2.cdf(stats_chi_sq, (len(obs) - params))


def r_squared(y_data, fitted_data):
    """R^2 calculation for linear model."""
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
    # Protect against division by zero when x + KD ≈ 0
    return np.array([x * f[0] / max(x + f[1], 1e-10) for x in c_list])


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
    # Input validation
    if len(c_list) != len(s_list):
        logger.error(
            f"Mismatched data lengths: c_list={len(c_list)}, s_list={len(s_list)}",
        )
        return None
    if len(c_list) < 3:
        logger.error(f"Insufficient data points for affinity fitting: {len(c_list)}")
        return None
    if max(s_list) <= 0 or max(c_list) <= 0:
        logger.error("Invalid data: all concentrations or shifts are non-positive")
        return None

    try:
        params = 2
        init_params = np.array([max(s_list), max(c_list) / 2])  # Rmax, KD
        res = minimize(
            fun=partial(affinity_est_func, c_list, s_list, params),
            x0=init_params,
            method="slsqp",
            options={"ftol": DEFAULT_FTOL, "disp": False},
        )

        if not res.success:
            logger.warning(f"Affinity optimization did not converge: {res.message}")

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
    except Exception as e:
        logger.error(f"Affinity optimization failed: {e}")
        return None


def optimize_by_linear(xdata, ydata):
    # Input validation
    if len(xdata) != len(ydata):
        logger.error(f"Mismatched data lengths: xdata={len(xdata)}, ydata={len(ydata)}")
        return None
    if len(xdata) < 2:
        logger.error(f"Insufficient data points for linear fitting: {len(xdata)}")
        return None

    try:
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
            f"Linear result: a = {result['a']}, b = {result['b']}, Rsq = {result['r_sq']}",
        )
        return result
    except Exception as e:
        logger.error(f"Linear optimization failed: {e}")
        return None


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
        ],
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
    # Input validation
    if len(xdata) != len(ydata):
        logger.error(f"Mismatched data lengths: xdata={len(xdata)}, ydata={len(ydata)}")
        return None
    if len(xdata) < 3:
        logger.error(f"Insufficient data points for association fitting: {len(xdata)}")
        return None

    try:
        params = 2
        init_params = np.array([ka0, rmax0])
        opt_val = minimize(
            fun=partial(assoc_est_func, xdata, ydata, c, kd, params),
            x0=init_params,
            method="slsqp",
            options={"ftol": DEFAULT_FTOL, "disp": False},
        )

        if not opt_val.success:
            logger.warning(
                f"Association optimization did not converge: {opt_val.message}",
            )

        return {"ka": opt_val.x[0], "rmax": opt_val.x[1]}
    except Exception as e:
        logger.error(f"Association optimization failed: {e}")
        return None


def func_rmax(data, r):
    """:param data: [c_data, kd]
    :param r: [rmax]
    """
    # Protect against division by zero
    return np.array(
        [
            (data[0][i] * r[0]) / max(data[0][i] + data[1], 1e-10)
            for i in range(len(data[0]))
        ],
    )


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
    # Input validation
    if len(c_data) != len(shift_data):
        logger.error(
            f"Mismatched data lengths: c_data={len(c_data)}, shift_data={len(shift_data)}",
        )
        return None
    if len(c_data) < 2:
        logger.error(f"Insufficient data points for Rmax fitting: {len(c_data)}")
        return None

    try:
        params = 1
        init_params = np.array([rmax0])
        opt_val = minimize(
            fun=partial(rmax_est_func, c_data, shift_data, kd, params),
            x0=init_params,
            method="slsqp",
            options={"ftol": DEFAULT_FTOL, "disp": False},
        )

        if not opt_val.success:
            logger.warning(f"Rmax optimization did not converge: {opt_val.message}")

        return {"rmax": opt_val.x[0]}
    except Exception as e:
        logger.error(f"Rmax optimization failed: {e}")
        return None
