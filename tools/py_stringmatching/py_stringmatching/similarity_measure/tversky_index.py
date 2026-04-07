"""Tversky index similarity measure"""

from py_stringmatching import utils
from py_stringmatching.similarity_measure.token_similarity_measure import \
                                                    TokenSimilarityMeasure


class TverskyIndex(TokenSimilarityMeasure):
    """Tversky index similarity measure class.

    Parameters:
        alpha, beta (float): Tversky index parameters (defaults to 0.5).
    """
    def __init__(self, alpha=0.5, beta=0.5):
        # validate alpha and beta 
        utils.sim_check_tversky_parameters(alpha, beta)

        self.alpha = alpha
        self.beta = beta
        super(TverskyIndex, self).__init__()

    def get_raw_score(self, set1, set2):
        """
        Computes the Tversky index similarity between two sets.

        The Tversky index is an asymmetric similarity measure on sets that compares a variant to a prototype. The
        Tversky index can be seen as a generalization of Dice's coefficient and Tanimoto coefficient.

        For sets X and Y the Tversky index is a number between 0 and 1 given by:
        :math:`tversky_index(X, Y) = \\frac{|X \\cap Y|}{|X \\cap Y| + \alpha |X-Y| + \beta |Y-X|}`
        where, :math: \alpha, \beta >=0

        Args:
            set1,set2 (set or list): Input sets (or lists). Input lists are converted to sets.

        Returns:
            Tversly index similarity (float)

        Raises:
            TypeError : If the inputs are not sets (or lists) or if one of the inputs is None.

        Examples:
            >>> tvi = TverskyIndex()
            >>> tvi.get_raw_score(['data', 'science'], ['data'])
            0.6666666666666666
            >>> tvi.get_raw_score(['data', 'management'], ['data', 'data', 'science'])
            0.5
            >>> tvi.get_raw_score({1, 1, 2, 3, 4}, {2, 3, 4, 5, 6, 7, 7, 8})
            0.5454545454545454
            >>> tvi = TverskyIndex(0.5, 0.5)
            >>> tvi.get_raw_score({1, 1, 2, 3, 4}, {2, 3, 4, 5, 6, 7, 7, 8})
            0.5454545454545454
            >>> tvi = TverskyIndex(beta=0.5)
            >>> tvi.get_raw_score(['data', 'management'], ['data', 'data', 'science'])
            0.5
        """
        # input validations
        utils.sim_check_for_none(set1, set2)
        utils.sim_check_for_list_or_set_inputs(set1, set2)

        # if exact match return 1.0
        if utils.sim_check_for_exact_match(set1, set2):
            return 1.0

        # if one of the strings is empty return 0
        if utils.sim_check_for_empty(set1, set2):
            return 0

        if not isinstance(set1, set):
            set1 = set(set1)
        if not isinstance(set2, set):
            set2 = set(set2)
        intersection = float(len(set1 & set2))

        return 1.0 * intersection / (intersection +
            (self.alpha * len(set1 - set2)) + (self.beta * len(set2 - set1)))

    def get_sim_score(self, set1, set2):
        """
        Computes the normalized tversky index similarity between two sets.

        Args:
            set1,set2 (set or list): Input sets (or lists). Input lists are converted to sets.

        Returns:
            Normalized tversky index similarity (float)

        Raises:
            TypeError : If the inputs are not sets (or lists) or if one of the inputs is None.

        Examples:
            >>> tvi = TverskyIndex()
            >>> tvi.get_sim_score(['data', 'science'], ['data'])
            0.6666666666666666
            >>> tvi.get_sim_score(['data', 'management'], ['data', 'data', 'science'])
            0.5
            >>> tvi.get_sim_score({1, 1, 2, 3, 4}, {2, 3, 4, 5, 6, 7, 7, 8})
            0.5454545454545454
            >>> tvi = TverskyIndex(0.5, 0.5)
            >>> tvi.get_sim_score({1, 1, 2, 3, 4}, {2, 3, 4, 5, 6, 7, 7, 8})
            0.5454545454545454
            >>> tvi = TverskyIndex(beta=0.5)
            >>> tvi.get_sim_score(['data', 'management'], ['data', 'data', 'science'])
            0.5

        """
        return self.get_raw_score(set1, set2)

    def get_alpha(self):
        """
        Get alpha

        Returns:
            alpha (float)
        """
        return self.alpha

    def get_beta(self):
        """
        Get beta

        Returns:
            beta (float)
        """
        return self.beta

    def set_alpha(self, alpha):
        """
        Set alpha

        Args:
            alpha (float): Tversky index parameter
        """
        self.alpha = alpha
        return True

    def set_beta(self, beta):
        """
        Set beta

        Args:
            beta (float): Tversky index parameter
        """
        self.beta = beta
        return True
