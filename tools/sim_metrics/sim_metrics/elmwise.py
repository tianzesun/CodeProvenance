import numpy as np


def ae(sim, obs):
    """Computes the absolute error.

    Args:
        sim (List[float]): Simulated values
        obs (List[float]): Observed values

    Returns:
        (List[float]): absolute error between sim and obs
    """
    return np.abs(np.array(obs) - np.array(sim))


def mae(sim, obs):
    """Computes the mean absolute error.

    Args:
        sim (List[float]): Simulated values
        obs (List[float]): Observed values

    Returns:
        (float): The mean absolute error between sim and obs
    """
    return np.mean(ae(sim, obs))


def se(sim, obs):
    """Computes the squared error.

    Args:
        sim (List[float]): Simulated values
        obs (List[float]): Observed values

    Returns:
        (List[float]): squared error between sim and obs
    """
    return np.power(np.array(obs) - np.array(sim), 2)


def mse(sim, obs):
    """Computes the mean squared error.

    Args:
        sim (List[float]): Simulated values
        obs (List[float]): Observed values

    Returns:
        (float): The mean squared error between sim and obs
    """
    return np.mean(se(sim, obs))


def rmse(sim, obs):
    """Computes the root mean squared error.

    Args:
        sim (List[float]): Simulated values
        obs (List[float]): Observed values

    Returns:
        (float): The root mean squared error between sim and obs
    """
    return np.sqrt(mse(sim, obs))


def rrmse(sim, obs):
    """Computes the relative root mean squared error.

    Args:
        sim (List[float]): Simulated values
        obs (List[float]): Observed values

    Returns:
        (float): The relative root mean squared error between sim and obs
    """
    return rmse(sim, obs) / abs(np.mean(obs))
