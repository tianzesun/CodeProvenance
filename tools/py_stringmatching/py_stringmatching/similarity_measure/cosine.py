import math

from py_stringmatching import utils
from py_stringmatching.similarity_measure.token_similarity_measure import \
                                                    TokenSimilarityMeasure


class Cosine(TokenSimilarityMeasure):
    """Computes a variant of cosine measure known as Ochiai coefficient.

    This is not the cosine measure that computes the cosine of the angle between two given vectors. Rather, it computes a variant of cosine measure known as Ochiai coefficient (see the Wikipedia page "Cosine Similarity"). Specifically, for two sets X and Y, this measure computes:

        :math:`cosine(X, Y) = \\frac{|X \\cap Y|}{\\sqrt{|X| \\cdot |Y|}}`
        
    Note:
        * In the case where one of X and Y is an empty set and the other is a non-empty set, we define their cosine score to be 0.
        * In the case where both X and Y are empty sets, we define their cosine score to be 1. 
    """

    def __init__(self):
        super(Cosine, self).__init__()

    def get_raw_score(self, set1, set2):
        """Computes the raw cosine score between two sets.

        Args:
            set1,set2 (set or list): Input sets (or lists). Input lists are converted to sets.

        Returns:
            Cosine similarity (float)

        Raises:
            TypeError : If the inputs are not sets (or lists) or if one of the inputs is None.

        Examples:
            >>> cos = Cosine()
            >>> cos.get_raw_score(['data', 'science'], ['data'])
            0.7071067811865475
            >>> cos.get_raw_score(['data', 'data', 'science'], ['data', 'management'])
            0.4999999999999999
            >>> cos.get_raw_score([], ['data'])
            0.0

        References:
            * String similarity joins: An Experimental Evaluation (a paper appearing in the VLDB 2014 Conference).
            * Project Flamingo at http://flamingo.ics.uci.edu.
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

        return float(len(set1 & set2)) / (math.sqrt(float(len(set1))) *
                                          math.sqrt(float(len(set2))))

    def get_sim_score(self, set1, set2):
        """Computes the normalized cosine similarity between two sets.

        Args:
            set1,set2 (set or list): Input sets (or lists). Input lists are converted to sets.

        Returns:
            Normalized cosine similarity (float)

        Raises:
            TypeError : If the inputs are not sets (or lists) or if one of the inputs is None.

        Examples:
            >>> cos = Cosine()
            >>> cos.get_sim_score(['data', 'science'], ['data'])
            0.7071067811865475
            >>> cos.get_sim_score(['data', 'data', 'science'], ['data', 'management'])
            0.4999999999999999
            >>> cos.get_sim_score([], ['data'])
            0.0

        """
        return self.get_raw_score(set1, set2)
