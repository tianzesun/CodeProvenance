"""Soundex phonetic similarity measure"""

import re

from py_stringmatching import utils
from py_stringmatching.similarity_measure.phonetic_similarity_measure import \
                                                    PhoneticSimilarityMeasure


class Soundex(PhoneticSimilarityMeasure):
    """Soundex phonetic similarity measure class.
    """
    def __init__(self):
        super(Soundex, self).__init__()

    def get_raw_score(self, string1, string2):
        """
        Computes the Soundex phonetic similarity between two strings.

        Phonetic measure such as soundex match string based on their sound. These
        measures have been especially effective in matching names, since names are
        often spelled in different ways that sound the same. For example, Meyer, Meier,
        and Mire sound the same, as do Smith, Smithe, and Smythe.

        Soundex is used primarily to match surnames. It does not work as well for names
        of East Asian origins, because much of the discriminating power of these names
        resides in the vowel sounds, which the code ignores.

        Args:
            string1,string2 (str): Input strings

        Returns:
            Soundex similarity score (int) is returned

        Raises:
            TypeError : If the inputs are not strings

        Examples:
            >>> s = Soundex()
            >>> s.get_raw_score('Robert', 'Rupert')
            1
            >>> s.get_raw_score('Sue', 's')
            1
            >>> s.get_raw_score('Gough', 'Goff')
            0
            >>> s.get_raw_score('a,,li', 'ali')
            1

        """
        # input validations
        utils.sim_check_for_none(string1, string2)
        utils.sim_check_for_string_inputs(string1, string2)

        # remove all chars but alphanumeric characters
        string1 = re.sub("[^a-zA-Z0-9]", "", string1)
        string2 = re.sub("[^a-zA-Z0-9]", "", string2)

        utils.sim_check_for_zero_len(string1, string2)

        if utils.sim_check_for_exact_match(string1, string2):
            return 1

        string1, string2 = string1.upper(), string2.upper()
        first_letter1, first_letter2 = string1[0], string2[0]
        string1, string2 = string1[1:], string2[1:]

        # remove occurrences of vowels, 'y', 'w' and 'h'
        string1 = re.sub('[AEIOUYWH]', '', string1)
        string2 = re.sub('[AEIOUYWH]', '', string2)

        # replace (B,F,P,V)->1 (C,G,J,K,Q,S,X,Z)->2 (D,T)->3 (L)->4
        # (M,N)->5 (R)->6
        string1 = re.sub('[BFPV]', '1', string1)
        string1 = re.sub('[CGJKQSXZ]', '2', string1)
        string1 = re.sub('[DT]', '3', string1)
        string1 = re.sub('[L]', '4', string1)
        string1 = re.sub('[MN]', '5', string1)
        string1 = re.sub('[R]', '6', string1)

        string2 = re.sub('[BFPV]', '1', string2)
        string2 = re.sub('[CGJKQSXZ]', '2', string2)
        string2 = re.sub('[DT]', '3', string2)
        string2 = re.sub('[L]', '4', string2)
        string2 = re.sub('[MN]', '5', string2)
        string2 = re.sub('[R]', '6', string2)

        string1 = first_letter1 + string1[:3]
        string2 = first_letter2 + string2[:3]

        return 1 if string1 == string2 else 0

    def get_sim_score(self, string1, string2):
        """
        Computes the normalized soundex similarity between two strings.

        Args:
            string1,string2 (str): Input strings

        Returns:
            Normalized soundex similarity (int)

        Raises:
            TypeError : If the inputs are not strings or if one of the inputs is None.

        Examples:
            >>> s = Soundex()
            >>> s.get_sim_score('Robert', 'Rupert')
            1
            >>> s.get_sim_score('Sue', 's')
            1
            >>> s.get_sim_score('Gough', 'Goff')
            0
            >>> s.get_sim_score('a,,li', 'ali')
            1

        """
        return self.get_raw_score(string1, string2)
