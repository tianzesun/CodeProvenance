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
    
    def test_is_valid_item(self):
        # Valid Items
        self.assertTrue(restaurant.is_valid_item("HAMBURGER"))
        self.assertTrue(restaurant.is_valid_item("FRIES"))
        
        # Invalid Items
        self.assertFalse(restaurant.is_valid_item("PIZZA"))
        self.assertFalse(restaurant.is_valid_item("pizza"))
        self.assertFalse(restaurant.is_valid_item("H@7 D0G"))
        self.assertFalse(restaurant.is_valid_item(""))
        self.assertFalse(restaurant.is_valid_item("hamburger"))
        self.assertFalse(restaurant.is_valid_item("FrieS"))
    
    def test_can_be_combo(self):
        # Valid Combo Items
        self.assertTrue(restaurant.can_be_combo("HAMBURGER"))
        self.assertTrue(restaurant.can_be_combo("HOT DOG"))
        
        #Invalid Combo Items
        self.assertFalse(restaurant.can_be_combo("hamburger"))
        self.assertFalse(restaurant.can_be_combo("PIZZA"))
        self.assertFalse(restaurant.can_be_combo("H@MBURG3R"))
        self.assertFalse(restaurant.can_be_combo("pizza"))
        self.assertFalse(restaurant.can_be_combo("FRIES"))
        self.assertFalse(restaurant.can_be_combo("SODA"))
        self.assertFalse(restaurant.can_be_combo(""))
        
    def test_calculate_item_price(self):
        # Valid Items with Valid Quantities
        self.assertEqual(restaurant.calculate_item_price("HAMBURGER", 3), 52.5)
        self.assertEqual(restaurant.calculate_item_price("HOT DOG", 2), 21.0)
        
        # Valid Items with Invalid Quantities
        self.assertEqual(restaurant.calculate_item_price("HAMBURGER", -1), 0.0)
        self.assertEqual(restaurant.calculate_item_price("HOT DOG", 0), 0.0)
        
        # Invalid Items
        self.assertEqual(restaurant.calculate_item_price("ICE CREAM", 4), 0.0)
        self.assertEqual(restaurant.calculate_item_price("ice cream", 1), 0.0)
        self.assertEqual(restaurant.calculate_item_price("H@MBURG3R", 1), 0.0)
        self.assertEqual(restaurant.calculate_item_price("", 2), 0.0)
        self.assertEqual(restaurant.calculate_item_price("hamburger", 2), 0.0)
        
    def test_calculate_item_cost(self):
        # Valid Items with Valid Quantities
        self.assertEqual(restaurant.calculate_item_cost("HAMBURGER", 2), 7.0)
        self.assertEqual(restaurant.calculate_item_cost("HOT DOG", 3), 7.5)
        
        # Valid Items with Invalid Quantities
        self.assertEqual(restaurant.calculate_item_cost("HAMBURGER", -2), 0.0)
        self.assertEqual(restaurant.calculate_item_cost("HOT DOG", 0), 0.0)
        
        # Invalid Items
        self.assertEqual(restaurant.calculate_item_cost("SUSHI", 2), 0.0)
        self.assertEqual(restaurant.calculate_item_cost("sushi", 3), 0.0)
        self.assertEqual(restaurant.calculate_item_cost("H@MBURG3R", 3), 0.0)
        self.assertEqual(restaurant.calculate_item_cost("", 5), 0.0)
        self.assertEqual(restaurant.calculate_item_cost("hamburger", 1), 0.0)
        
    def test_calculate_combo_price(self):
        # Valid Combos with Valid Quantities
        self.assertEqual(restaurant.calculate_combo_price("HAMBURGER", 2), 52.0)
        self.assertEqual(restaurant.calculate_combo_price("HOT DOG", 3), 57.0)
        
        # Valid Combos with Invalid Quantities
        self.assertEqual(restaurant.calculate_combo_price("HAMBURGER", 0), 0.0)
        self.assertEqual(restaurant.calculate_combo_price("HOT DOG", -3), 0.0)
        
        # Invalid Combos
        self.assertEqual(restaurant.calculate_combo_price("COFFEE", 1), 0.0)
        self.assertEqual(restaurant.calculate_combo_price("coffee", 1), 0.0)
        self.assertEqual(restaurant.calculate_combo_price("H@MBURG3R", 2), 0.0)
        self.assertEqual(restaurant.calculate_combo_price("", 3), 0.0)
        self.assertEqual(restaurant.calculate_combo_price("hamburger", 9), 0.0)
        
    def test_calculate_combo_cost(self):
        # Valid Combos with Valid Quantities
        self.assertEqual(restaurant.calculate_combo_cost("HAMBURGER", 1), 7.5)
        self.assertEqual(restaurant.calculate_combo_cost("HOT DOG", 2), 13.0)
        
        # Valid Combos with Invalid Quantities
        self.assertEqual(restaurant.calculate_combo_cost("HAMBURGER", -9), 0.0)
        self.assertEqual(restaurant.calculate_combo_cost("HOT DOG", 0), 0.0)
        
        # Invalid Combos
        self.assertEqual(restaurant.calculate_combo_cost("ROTI", 2), 0.0)
        self.assertEqual(restaurant.calculate_combo_cost("roti", 2), 0.0)
        self.assertEqual(restaurant.calculate_combo_cost("H@MBURG3R", 10), 0.0)
        self.assertEqual(restaurant.calculate_combo_cost("", 2), 0.0)
        self.assertEqual(restaurant.calculate_combo_cost("hamburger", 67), 0.0)
    
    def test_get_item_from_sentence(self):
        # Valid Sentences
        self.assertEqual(restaurant.get_item_from_sentence("Please give me a FRIES."), "FRIES")
        self.assertEqual(restaurant.get_item_from_sentence("Can I have a HAMBURGER combo?"), "COMBO HAMBURGER")
        
        # Invalid Sentences
        self.assertEqual(restaurant.get_item_from_sentence("Can I have some PASTA?"), "UNKNOWN")
        self.assertEqual(restaurant.get_item_from_sentence("Can I have a H@MBURG3R combo?"), "UNKNOWN")
        self.assertEqual(restaurant.get_item_from_sentence(""), "UNKNOWN")
        self.assertEqual(restaurant.get_item_from_sentence("Where is the washroom?"), "UNKNOWN")
        self.assertEqual(restaurant.get_item_from_sentence("please give me a fries."), "UNKNOWN")
        self.assertEqual(restaurant.get_item_from_sentence("CAN I HAVE A HAMBURGER COMBO!"), "UNKNOWN")
        self.assertEqual(restaurant.get_item_from_sentence("HAMBURGER COMBO!"), "UNKNOWN")
        self.assertEqual(restaurant.get_item_from_sentence("HAMBURGER"), "UNKNOWN")

if __name__ == '__main__':
    unittest.main()
