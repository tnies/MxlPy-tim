"""Numerical parameter identification estimations."""

from functools import partial

import numpy as np
import pandas as pd
from tqdm import tqdm

from mxlpy import fit
from mxlpy.distributions import LogNormal, sample
from mxlpy.model import Model
from mxlpy.parallel import parallelise
from mxlpy.types import Array

__all__ = ["profile_likelihood"]


def _mc_fit_time_course_worker(
    p0: pd.Series,
    model: Model,
    data: pd.DataFrame,
) -> float:
    p_fit = fit.time_course(model=model, p0=p0.to_dict(), data=data)
    return fit._time_course_residual(  # noqa: SLF001
        par_values=list(p_fit.values()),
        par_names=list(p_fit.keys()),
        data=data,
        model=model,
        y0=None,
        integrator=fit.DefaultIntegrator,
    )


def profile_likelihood(
    model: Model,
    data: pd.DataFrame,
    parameter_name: str,
    parameter_values: Array,
    n_random: int = 10,
) -> pd.Series:
    """Estimate the profile likelihood of model parameters given data.

    Args:
        model: The model to be fitted.
        data: The data to fit the model to.
        parameter_name: The name of the parameter to profile.
        parameter_values: The values of the parameter to profile.
        n_random: Number of Monte Carlo samples.

    """
    parameter_distributions = sample(
        {k: LogNormal(np.log(v), sigma=1) for k, v in model.parameters.items()},
        n=n_random,
    )

    res = {}
    for value in tqdm(parameter_values, desc=parameter_name):
        model.update_parameter(parameter_name, value)
        res[value] = parallelise(
            partial(_mc_fit_time_course_worker, model=model, data=data),
            inputs=list(
                parameter_distributions.drop(columns=parameter_name).iterrows()
            ),
            disable_tqdm=True,
        )
    errors = pd.DataFrame(res, dtype=float).T.abs().mean(axis=1)
    errors.index.name = "fitting error"
    return errors
