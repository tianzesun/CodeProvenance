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
        
    ########################################################################

    def test_is_valid_item_invalid_item(self):
        act = restaurant.is_valid_item("WATER")
        exp = False
        self.assertEqual(act, exp)
    
    def test_is_valid_item_valid_item_and_combo_item(self):
        act = restaurant.is_valid_item("HAMBURGER")
        exp = True
        self.assertEqual(act, exp)
        
    def test_is_valid_item_lowercase_valid_item(self):
        act = restaurant.is_valid_item("hamburger")
        exp = False
        self.assertEqual(act, exp)
    
    def test_is_valid_item_empty_string(self):
        act = restaurant.is_valid_item("")
        exp = False
        self.assertEqual(act, exp)
    
    def test_is_valid_item_valid_item_and_noncombo_item(self):
        act = restaurant.is_valid_item("SODA")
        exp = True
        self.assertEqual(act, exp)    
        
    ########################################################################
    
    def test_can_be_combo_valid_combo_item(self):
        act = restaurant.can_be_combo("HAMBURGER")
        exp = True
        self.assertEqual(act, exp)
    
    def test_can_be_combo_valid_item_but_invalid_combo_item(self):
        act = restaurant.can_be_combo("FRIES")
        exp = False
        self.assertEqual(act, exp)
    
    def test_can_be_combo__valid_combo_item_withs_space(self):
        act = restaurant.can_be_combo("HOT DOG")
        exp = True
        self.assertEqual(act, exp)
    
    def test_can_be_combo_valid_combo_item_lowercase(self):
        act = restaurant.can_be_combo("hamburger")
        exp = False
        self.assertEqual(act, exp)    
    
    def test_can_be_combo_empty_string(self):
        act = restaurant.can_be_combo("")
        exp = False
        self.assertEqual(act, exp)   
    
    ########################################################################
    
    def test_calculate_item_price_valid_iten_0(self):
        act = restaurant.calculate_item_price("HAMBURGER", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_price_valid_iten_negative(self):
        act = restaurant.calculate_item_price("HAMBURGER", -1)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_price_invalid_iten_0(self):
        act = restaurant.calculate_item_price("FISH", 0)
        exp = 0.0
        self.assertEqual(act, exp)
        
    def test_calculate_item_price_invalid_iten_negative(self):
        act = restaurant.calculate_item_price("FISH", -2)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_price_valid_iten_positive(self):
        act = restaurant.calculate_item_price("HAMBURGER", 3)
        exp = 52.5
        self.assertEqual(act, exp)
    
    def test_calculate_item_price_invalid_iten_positive(self):
        act = restaurant.calculate_item_price("FISH", 3)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_price_example_7(self):
        act = restaurant.calculate_item_price("SODA", 1)
        exp = 2.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_price_example_8(self):
        act = restaurant.calculate_item_price("SODA", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_price_example_9(self):
        act = restaurant.calculate_item_price("SODA", -3)
        exp = 0.0
        self.assertEqual(act, exp)       
        
    ########################################################################
    
    def test_calculate_item_cost_example_1(self):
        act = restaurant.calculate_item_cost("HAMBURGER", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_cost_example_2(self):
        act = restaurant.calculate_item_cost("HAMBURGER", -1)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_cost_example_3(self):
        act = restaurant.calculate_item_cost("FISH", 0)
        exp = 0.0
        self.assertEqual(act, exp)
        
    def test_calculate_item_cost_example_4(self):
        act = restaurant.calculate_item_cost("FISH", -2)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_cost_example_5(self):
        act = restaurant.calculate_item_cost("HAMBURGER", 3)
        exp = 10.5
        self.assertEqual(act, exp)
    
    def test_calculate_item_cost_example_6(self):
        act = restaurant.calculate_item_cost("FISH", 3)
        exp = 0.0
        self.assertEqual(act, exp)
        
    def test_calculate_item_cost_example_7(self):
        act = restaurant.calculate_item_cost("SODA", 1)
        exp = 1.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_cost_example_8(self):
        act = restaurant.calculate_item_cost("SODA", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_item_cost_example_9(self):
        act = restaurant.calculate_item_cost("SODA", -3)
        exp = 0.0
        self.assertEqual(act, exp)     

    ########################################################################
    
    def test_calculate_combo_price_example_1(self):
        act =  restaurant.calculate_combo_price("HAMBURGER", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_price_example_2(self):
        act =  restaurant.calculate_combo_price("HAMBURGER", 3)
        exp = 78.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_price_example_3(self):
        act =  restaurant.calculate_combo_price("HAMBURGER", -2)
        exp = 0.0
        self.assertEqual(act, exp)
        
    def test_calculate_combo_price_example_4(self):
        act =  restaurant.calculate_combo_price("PIZZA", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_price_example_5(self):
        act =  restaurant.calculate_combo_price("PIZZA", 3)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_price_example_6(self):
        act =  restaurant.calculate_combo_price("PIZZA", -3)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_price_example_7(self):
        act =  restaurant.calculate_combo_price("FRIES", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_price_example_8(self):
        act =  restaurant.calculate_combo_price("FRIES", 3)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_price_example_9(self):
        act =  restaurant.calculate_combo_price("FRIES", -3)
        exp = 0.0
        self.assertEqual(act, exp)    

    ########################################################################
    
    def test_calculate_combo_cost_example_1(self):
        act =  restaurant.calculate_combo_cost("HAMBURGER", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_cost_example_2(self):
        act =  restaurant.calculate_combo_cost("HAMBURGER", 3)
        exp = 22.5
        self.assertEqual(act, exp)
    
    def test_calculate_combo_cost_example_3(self):
        act =  restaurant.calculate_combo_cost("HAMBURGER", -2)
        exp = 0.0
        self.assertEqual(act, exp)
        
    def test_calculate_combo_cost_example_4(self):
        act =  restaurant.calculate_combo_cost("PIZZA", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_cost_example_5(self):
        act =  restaurant.calculate_combo_cost("PIZZA", 3)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_cost_example_6(self):
        act =  restaurant.calculate_combo_cost("PIZZA", -3)
        exp = 0.0
        self.assertEqual(act, exp) 
    
    def test_calculate_combo_cost_example_7(self):
        act =  restaurant.calculate_combo_cost("FRIES", 0)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_cost_example_8(self):
        act =  restaurant.calculate_combo_cost("SODA", 3)
        exp = 0.0
        self.assertEqual(act, exp)
    
    def test_calculate_combo_cost_example_9(self):
        act =  restaurant.calculate_combo_cost("SODA", -3)
        exp = 0.0
        self.assertEqual(act, exp)     

    ########################################################################
    
    def test_get_item_from_sentence_example_1(self):
        act =  restaurant.get_item_from_sentence("Please give me a FRIES.")
        exp = "FRIES"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_2(self):
        act =  restaurant.get_item_from_sentence("Please give me a PIZZA.")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_3(self):
        act =  restaurant.get_item_from_sentence("Where is the washroom?")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_4(self):
        act =  restaurant.get_item_from_sentence("")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_5(self):
        act =  restaurant.get_item_from_sentence("Can I have a HAMBURGER?")
        exp = "HAMBURGER"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_6(self):
        act =  restaurant.get_item_from_sentence("Can I have a PIZZA?")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)
        
    
    def test_get_item_from_sentence_example_7(self):
        act =  restaurant.get_item_from_sentence("Can I have a HAMBURGER combo?")
        exp = "COMBO HAMBURGER"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_8(self):
        act =  restaurant.get_item_from_sentence("Can I have a FRIES combo?")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_9(self):
        act =  restaurant.get_item_from_sentence("Can I have a PIZZA combo?")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_10(self):
        act =  restaurant.get_item_from_sentence("Please give me a combo of FRIES.")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_11(self):
        act =  restaurant.get_item_from_sentence("Please give me a combo of HAMBURGER.")
        exp = "COMBO HAMBURGER"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_12(self):
        act =  restaurant.get_item_from_sentence("Please give me a combo of PIZZA.")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)    
    
    def test_get_item_from_sentence_example_13(self):
        act =  restaurant.get_item_from_sentence("COMBO HAMBURGER")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)
    
    def test_get_item_from_sentence_example_14(self):
        act =  restaurant.get_item_from_sentence("FRIES")
        exp = "UNKNOWN"
        self.assertEqual(act, exp)    
        
        
if __name__ == '__main__':
    unittest.main()
