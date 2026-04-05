"""
CSCA08: Winter 2024 -- Assignment 3: Wacky's Michelin Restaurant

This code is provided solely for the personal and private use of
students taking the CSCA08 course at the University of
Toronto. Copying for purposes other than this use is expressly
prohibited. All forms of distribution of this code, whether as given
or with any changes, are expressly prohibited.
"""

import unittest
import restaurant

class TestRestaurant(unittest.TestCase):

    def test_get_restaurant_name_valid(self):
        self.assertEqual(restaurant.get_restaurant_name(), "Wacky's Restaurant")

class TestIsValidItem(unittest.TestCase):

    def test_is_valid_item(self):

        actual = [
            restaurant.is_valid_item("HAMBURGER"),
            restaurant.is_valid_item("HOT DOG"),
            restaurant.is_valid_item("FRIES"),
            restaurant.is_valid_item("SODA"),
            restaurant.is_valid_item("WATER"),
            restaurant.is_valid_item("hamburger"),
            restaurant.is_valid_item("hot dog"),
            restaurant.is_valid_item("fries"),
            restaurant.is_valid_item("soda"),
            restaurant.is_valid_item("HAMBURGER    "),
            restaurant.is_valid_item("HOT DOG    "),
            restaurant.is_valid_item("FRIES    "),
            restaurant.is_valid_item("SODA    "),
            restaurant.is_valid_item("HOT FRIES"),
            restaurant.is_valid_item("HOT DOG SODA"),
            restaurant.is_valid_item("SODA HAMBURGER"),
        ]

        expected = [True, True, True, True,
                    False, False, False, False,
                    False, False, False, False,
                    False, False, False, False]

        for i in range(len(actual)):
            self.assertEqual(actual[i], expected[i])

        
class TestCanBeCombo(unittest.TestCase):

    def test_can_be_combo(self):

        actual = [
            restaurant.can_be_combo("HAMBURGER"),
            restaurant.can_be_combo("HOT DOG"),
            restaurant.can_be_combo("FRIES"),
            restaurant.can_be_combo("SODA"),
            restaurant.can_be_combo("WATER"),
            restaurant.can_be_combo("hamburger"),
            restaurant.can_be_combo("hot dog"),
            restaurant.can_be_combo("fries"),
            restaurant.can_be_combo("soda"),
            restaurant.can_be_combo("HAMBURGER    "),
            restaurant.can_be_combo("HOT DOG    "),
            restaurant.can_be_combo("FRIES    "),
            restaurant.can_be_combo("SODA    "),
            restaurant.can_be_combo("HOT FRIES"),
            restaurant.can_be_combo("HOT DOG SODA"),
            restaurant.can_be_combo("SODA HAMBURGER"),
        ]

        expected = [True, True, False, False,
                    False, False, False, False,
                    False, False, False, False,
                    False, False, False, False]

        for i in range(len(actual)):
            self.assertEqual(actual[i], expected[i])

        

class TestCalculateItemPrice(unittest.TestCase):
    """Test functions for calculate_item_price"""

    def test_calculate_item_price(self):
        actual = [
            restaurant.calculate_item_price("HAMBURGER", 3),
            restaurant.calculate_item_price("HOTDOG", 5),
            restaurant.calculate_item_price("FRIES", 3),
            restaurant.calculate_item_price("SODA", 5),
            restaurant.calculate_item_price("HAMBURGER", 0),
            restaurant.calculate_item_price("HOTDOG", 0),
            restaurant.calculate_item_price("FRIES", 0),
            restaurant.calculate_item_price("SODA", 0),
            restaurant.calculate_item_price("HAMBURGER", -1),
            restaurant.calculate_item_price("HOTDOG", -1),
            restaurant.calculate_item_price("FRIES", -1),
            restaurant.calculate_item_price("SODA", -1),
            restaurant.calculate_item_price("WATER", 1),
            restaurant.calculate_item_price("WATER", 0),
            restaurant.calculate_item_price("WATER", -1),
            restaurant.calculate_item_price("", 1),
            restaurant.calculate_item_price("", 0),
            restaurant.calculate_item_price("", -1),
        ]

        expected = [52.5, 0.0, 22.5, 10.0,
                    0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0]

        for i in range(len(actual)):
            self.assertEqual(actual[i], expected[i])

class TestCalculateItemCost(unittest.TestCase):
    """Test functions for calculate_item_cost"""

    def test_calculate_item_cost(self):
        actual = [
            restaurant.calculate_item_cost("HAMBURGER", 3),
            restaurant.calculate_item_cost("HOTDOG", 5),
            restaurant.calculate_item_cost("FRIES", 3),
            restaurant.calculate_item_cost("SODA", 5),
            restaurant.calculate_item_cost("HAMBURGER", 0),
            restaurant.calculate_item_cost("HOTDOG", 0),
            restaurant.calculate_item_cost("FRIES", 0),
            restaurant.calculate_item_cost("SODA", 0),
            restaurant.calculate_item_cost("HAMBURGER", -1),
            restaurant.calculate_item_cost("HOTDOG", -1),
            restaurant.calculate_item_cost("FRIES", -1),
            restaurant.calculate_item_cost("SODA", -1),
            restaurant.calculate_item_cost("WATER", 1),
            restaurant.calculate_item_cost("WATER", 0),
            restaurant.calculate_item_cost("WATER", -1),
            restaurant.calculate_item_cost("", 1),
            restaurant.calculate_item_cost("", 0),
            restaurant.calculate_item_cost("", -1),
        ]

        expected = [10.5, 0.0, 9.0, 5.0,
                    0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0]

        for i in range(len(actual)):
            self.assertEqual(actual[i], expected[i])

class TestCalculateComboPrice(unittest.TestCase):
    """Test functions for calculate_combo_price"""

    def test_calculate_combo_price(self):
        actual = [
            restaurant.calculate_combo_price('HAMBURGER', 3),
            restaurant.calculate_combo_price('FRIES', 3),
            restaurant.calculate_combo_price('HOT DOG', 3),
            restaurant.calculate_combo_price('SODA', 3),
            restaurant.calculate_combo_price('WATER', 3),
            restaurant.calculate_combo_price('HAMBURGER', 0),
            restaurant.calculate_combo_price('FRIES', 0),
            restaurant.calculate_combo_price('HOT DOG', 0),
            restaurant.calculate_combo_price('SODA', 0),
            restaurant.calculate_combo_price('WATER', 0),
            restaurant.calculate_combo_price('HAMBURGER', -1),
            restaurant.calculate_combo_price('FRIES', -1),
            restaurant.calculate_combo_price('HOT DOG', -1),
            restaurant.calculate_combo_price('SODA', -1),
            restaurant.calculate_combo_price('WATER', -1),
            restaurant.calculate_combo_price(' ', 1),
            restaurant.calculate_combo_price(' ', 0),
            restaurant.calculate_combo_price(' ', -1),
        ]

        expected = [78.0, 0.0, 57.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0]
        
        for i in range(len(actual)):
            self.assertEqual(actual[i], expected[i])        

class TestCalculateComboCost(unittest.TestCase):
    """Test functions for calculate_combo_cost"""

    def test_calculate_combo_cost(self):
        actual = [
            restaurant.calculate_combo_cost('HAMBURGER', 3),
            restaurant.calculate_combo_cost('FRIES', 3),
            restaurant.calculate_combo_cost('HOT DOG', 3),
            restaurant.calculate_combo_cost('SODA', 3),
            restaurant.calculate_combo_cost('WATER', 3),
            restaurant.calculate_combo_cost('HAMBURGER', 0),
            restaurant.calculate_combo_cost('FRIES', 0),
            restaurant.calculate_combo_cost('HOT DOG', 0),
            restaurant.calculate_combo_cost('SODA', 0),
            restaurant.calculate_combo_cost('WATER', 0),
            restaurant.calculate_combo_cost('HAMBURGER', -1),
            restaurant.calculate_combo_cost('FRIES', -1),
            restaurant.calculate_combo_cost('HOT DOG', -1),
            restaurant.calculate_combo_cost('SODA', -1),
            restaurant.calculate_combo_cost('WATER', -1),
            restaurant.calculate_combo_cost(' ', 1),
            restaurant.calculate_combo_cost(' ', 0),
            restaurant.calculate_combo_cost(' ', -1),
        ]

        expected = [22.5, 0.0, 19.5, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0]
        
        for i in range(len(actual)):
            self.assertEqual(actual[i], expected[i])

class TestGetItemFromSentence(unittest.TestCase):
    """Test functions for get_item_from_sentences"""

    def test_get_item_from_sentences(self):
        actual = [
            restaurant.get_item_from_sentence('Please give me a HAMBURGER.'),
            restaurant.get_item_from_sentence('Can I have a HAMBURGER?'),
            restaurant.get_item_from_sentence('Please give me a HOT DOG.'),
            restaurant.get_item_from_sentence('Can I have a HOT DOG?'),
            restaurant.get_item_from_sentence('Please give me a FRIES.'),
            restaurant.get_item_from_sentence('Can I have a FRIES?'),
            restaurant.get_item_from_sentence('Please give me a SODA.'),
            restaurant.get_item_from_sentence('Can I have a SODA?'),
            restaurant.get_item_from_sentence('Please give me a WATER.'),
            restaurant.get_item_from_sentence('Can I have a WATER?'),
            restaurant.get_item_from_sentence('Please give me a WATER.'),
            restaurant.get_item_from_sentence('Can I have a WATER?'),
            restaurant.get_item_from_sentence('Please give me a WATER.'),
            restaurant.get_item_from_sentence('Can I have a WATER?'),
            restaurant.get_item_from_sentence('Please give me a WATER.'),
            restaurant.get_item_from_sentence('Can I have a WATER?'),
            restaurant.get_item_from_sentence('Please give me a combo of HAMBURGER.'),
            restaurant.get_item_from_sentence('Can I have a HAMBURGER combo?'),
            restaurant.get_item_from_sentence('Please give me a combo of HOT DOG.'),
            restaurant.get_item_from_sentence('Can I have a HOT DOG combo?'),
            restaurant.get_item_from_sentence('Please give me a HAMBURGER HOT DOG.'),
            restaurant.get_item_from_sentence('Please give me a HAMBURGER SODA.'),
            restaurant.get_item_from_sentence('Please give me a SODA FRIES.'),
            restaurant.get_item_from_sentence('Please give me a soda.'),
            restaurant.get_item_from_sentence('Please give me a fries.'),
            restaurant.get_item_from_sentence('Please give me a hot dog.'),
            restaurant.get_item_from_sentence('Please give me a hamburger.'),
            restaurant.get_item_from_sentence('Hi! Please give me a HAMBURGER.'),
            restaurant.get_item_from_sentence('Please give me a HAMBURGER. Thank you!'),
            restaurant.get_item_from_sentence('Please give me a HAMBURGER.         '),
        ]

        expected = ['HAMBURGER', 'HAMBURGER', 'HOT DOG', 'HOT DOG', 'FRIES', 'FRIES', 'SODA', 'SODA', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'COMBO HAMBURGER', 'COMBO HAMBURGER', 'COMBO HOT DOG', 'COMBO HOT DOG', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN']

        for i in range(len(actual)):
            self.assertEqual(actual[i], expected[i])

    # get item from sentences
    """
    get_item_from_sentence("Please give me a FRIES.")
    do all sentences
    do all combos
    two words that are valid
    lowercase
    extra words at start
    end
    spaces

    """

if __name__ == '__main__':
    unittest.main()
