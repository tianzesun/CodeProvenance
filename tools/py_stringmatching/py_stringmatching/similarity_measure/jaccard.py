from py_stringmatching import utils
from py_stringmatching.similarity_measure.token_similarity_measure import \
                                                    TokenSimilarityMeasure


class Jaccard(TokenSimilarityMeasure):
    """Computes Jaccard measure.

     For two sets X and Y, the Jaccard similarity score is:

        :math:`jaccard(X, Y) = \\frac{|X \\cap Y|}{|X \\cup Y|}`
        
     Note:
         In the case where both X and Y are empty sets, we define their Jaccard score to be 1. 
    """

    def __init__(self):
        super(Jaccard, self).__init__()

    def get_raw_score(self, set1, set2):
        """Computes the raw Jaccard score between two sets.

        Args:
            set1,set2 (set or list): Input sets (or lists). Input lists are converted to sets.

        Returns:
            Jaccard similarity score (float).

        Raises:
            TypeError : If the inputs are not sets (or lists) or if one of the inputs is None.

        Examples:
            >>> jac = Jaccard()
            >>> jac.get_raw_score(['data', 'science'], ['data'])
            0.5
            >>> jac.get_raw_score({1, 1, 2, 3, 4}, {2, 3, 4, 5, 6, 7, 7, 8})
            0.375
            >>> jac.get_raw_score(['data', 'management'], ['data', 'data', 'science'])
            0.3333333333333333
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

        return float(len(set1 & set2)) / float(len(set1 | set2))

    def get_sim_score(self, set1, set2):
        """Computes the normalized Jaccard similarity between two sets. Simply call get_raw_score.

        Args:
            set1,set2 (set or list): Input sets (or lists). Input lists are converted to sets.

        Returns:
            Normalized Jaccard similarity (float).

        Raises:
            TypeError : If the inputs are not sets (or lists) or if one of the inputs is None.

        Examples:
            >>> jac = Jaccard()
            >>> jac.get_sim_score(['data', 'science'], ['data'])
            0.5
            >>> jac.get_sim_score({1, 1, 2, 3, 4}, {2, 3, 4, 5, 6, 7, 7, 8})
            0.375
            >>> jac.get_sim_score(['data', 'management'], ['data', 'data', 'science'])
            0.3333333333333333
        """
        return self.get_raw_score(set1, set2)
