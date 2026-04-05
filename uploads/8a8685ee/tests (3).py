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

#1        #IS_VALID_ITEM TESTS!!!!

    def test_is_valid_item_HB(self):
        #testing HAMBURGER
        actual = restaurant.is_valid_item('HAMBURGER')
        expected = True
        self.assertEqual(actual, expected)

    def test_is_valid_item_HD(self):
        #testing HOT DOG
        actual = restaurant.is_valid_item('HOT DOG')
        expected = True
        self.assertEqual(actual, expected)

    def test_is_valid_item_F(self):
        #testing FRIES
        actual = restaurant.is_valid_item('FRIES')
        expected = True
        self.assertEqual(actual, expected)

    def test_is_valid_item_S(self):
        #testing SODA
        actual = restaurant.is_valid_item('SODA')
        expected = True
        self.assertEqual(actual, expected)

    def test_is_valid_item_case_1(self):
        #testing case
        actual = restaurant.is_valid_item('hamburger')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_case_2(self):
        #testing case
        actual = restaurant.is_valid_item('Hamburger')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_case_3(self):
        #testing case
        actual = restaurant.is_valid_item('HAMBURGeR')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_case_4(self):
        #testing case
        actual = restaurant.is_valid_item('hamBurger')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_double(self):
        #testing case
        actual = restaurant.is_valid_item('SODASODA')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_sep(self):
        #testing case
        actual = restaurant.is_valid_item('HOTDOG')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_extra_1(self):
        #testing case
        actual = restaurant.is_valid_item('SODAHELLO')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_extra_2(self):
        #testing case
        actual = restaurant.is_valid_item('HELLOSODA')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_extra_3(self):
        #testing case
        actual = restaurant.is_valid_item(' SODA')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_partial(self):
        #testing partial
        actual = restaurant.is_valid_item('HAMBUR')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_empty(self):
        #testing case
        actual = restaurant.is_valid_item('')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_random(self):
        #testing case
        actual = restaurant.is_valid_item('HELLO')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_extra_3(self):
        #testing space
        actual = restaurant.is_valid_item(' HAMBURGER')
        expected = False
        self.assertEqual(actual, expected)

    def test_is_valid_item_extra_4(self):
        #testing space
        actual = restaurant.is_valid_item('HAMBURGER ')
        expected = False
        self.assertEqual(actual, expected)

 #2       #CAN_BE_COMBO TESTS!!!

    def test_can_be_combo_HB(self):
        #testing HAMBURGER
        actual = restaurant.can_be_combo('HAMBURGER')
        expected = True
        self.assertEqual(actual, expected)

    def test_can_be_combo_HD(self):
        #testing HOT DOG
        actual = restaurant.can_be_combo('HOT DOG')
        expected = True
        self.assertEqual(actual, expected)

    def test_can_be_combo_F(self):
        #testing FRIES
        actual = restaurant.can_be_combo('FRIES')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_S(self):
        #testing SODA
        actual = restaurant.can_be_combo('SODA')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_case_1(self):
        #testing case
        actual = restaurant.can_be_combo('hamburger')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_case_2(self):
        #testing case
        actual = restaurant.can_be_combo('Hamburger')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_case_3(self):
        #testing case
        actual = restaurant.can_be_combo('HAMBURGeR')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_case_4(self):
        #testing case
        actual = restaurant.can_be_combo('hamBurger')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_double(self):
        #testing double
        actual = restaurant.can_be_combo('HAMBURGERHAMBURGER')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_sep(self):
        #testing sep
        actual = restaurant.can_be_combo('HOTDOG')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_extra_1(self):
        #testing addon
        actual = restaurant.can_be_combo('HAMBURGERHELLO')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_extra_2(self):
        #testing addon
        actual = restaurant.can_be_combo('HELLOHAMBURGER')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_extra_3(self):
        #testing space
        actual = restaurant.can_be_combo(' HAMBURGER')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_extra_4(self):
        #testing space
        actual = restaurant.can_be_combo('HAMBURGER ')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_partial(self):
        #testing partial
        actual = restaurant.can_be_combo('HAMBUR')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_empty(self):
        #testing empty
        actual = restaurant.can_be_combo('')
        expected = False
        self.assertEqual(actual, expected)

    def test_can_be_combo_random(self):
        #testing empty
        actual = restaurant.can_be_combo('HELLO')
        expected = False
        self.assertEqual(actual, expected)

#3        #CALCULATE ITEM PRICE TESTS!!!

    def test_calculate_item_price_neg(self):
        actual = restaurant.calculate_item_price('HAMBURGER',-2)
        expected = 0.0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_ZERO(self):
        actual = restaurant.calculate_item_price('HAMBURGER',0)
        expected = 0.0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_HBone(self):
        actual = restaurant.calculate_item_price('HAMBURGER',1)
        expected = 17.50
        self.assertEqual(actual, expected)

    def test_calculate_item_price_HBtwo(self):
        actual = restaurant.calculate_item_price('HAMBURGER',2)
        expected = 35
        self.assertEqual(actual, expected)

    def test_calculate_item_price_HBthree(self):
        actual = restaurant.calculate_item_price('HAMBURGER',3)
        expected = 52.5
        self.assertEqual(actual, expected)

    def test_calculate_item_price_HBbig(self):
        actual = restaurant.calculate_item_price('HAMBURGER',12)
        expected = 210
        self.assertEqual(actual, expected)

    def test_calculate_item_price_HDone(self):
        actual = restaurant.calculate_item_price('HOT DOG',1)
        expected = 10.50
        self.assertEqual(actual, expected)

    def test_calculate_item_price_HDtwo(self):
        actual = restaurant.calculate_item_price('HOT DOG',2)
        expected = 21
        self.assertEqual(actual, expected)

    def test_calculate_item_price_HDthree(self):
        actual = restaurant.calculate_item_price('HOT DOG',3)
        expected = 31.5
        self.assertEqual(actual, expected)

    def test_calculate_item_price_HDbig(self):
        actual = restaurant.calculate_item_price('HOT DOG',12)
        expected = 126
        self.assertEqual(actual, expected)

    def test_calculate_item_price_Fone(self):
        actual = restaurant.calculate_item_price('FRIES',1)
        expected = 7.50
        self.assertEqual(actual, expected)

    def test_calculate_item_price_Ftwo(self):
        actual = restaurant.calculate_item_price('FRIES',2)
        expected = 15
        self.assertEqual(actual, expected)

    def test_calculate_item_price_Fthree(self):
        actual = restaurant.calculate_item_price('FRIES',3)
        expected = 22.5
        self.assertEqual(actual, expected)

    def test_calculate_item_price_Fbig(self):
        actual = restaurant.calculate_item_price('FRIES',12)
        expected = 90
        self.assertEqual(actual, expected)

    def test_calculate_item_price_Sone(self):
        actual = restaurant.calculate_item_price('SODA',1)
        expected = 2
        self.assertEqual(actual, expected)

    def test_calculate_item_price_Stwo(self):
        actual = restaurant.calculate_item_price('SODA',2)
        expected = 4
        self.assertEqual(actual, expected)

    def test_calculate_item_price_Sthree(self):
        actual = restaurant.calculate_item_price('SODA',3)
        expected = 6
        self.assertEqual(actual, expected)

    def test_calculate_item_price_Sbig(self):
        actual = restaurant.calculate_item_price('SODA',12)
        expected = 24
        self.assertEqual(actual, expected)

    def test_calculate_item_price_big(self):
        actual = restaurant.calculate_item_price('HAMBURGER',100)
        expected = 1750.0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_case_1(self):
        actual = restaurant.calculate_item_price('hamburger', 1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_case_2(self):
        actual = restaurant.calculate_item_price('Hamburger',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_3(self):
        actual = restaurant.calculate_item_price('HAMBURGeR',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_case_4(self):
        actual = restaurant.calculate_item_price('hamBurger',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_double(self):
        actual = restaurant.calculate_item_price('HAMBURGERHAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_sep(self):
        actual = restaurant.calculate_item_price('HOTDOG',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_extra_1(self):
        actual = restaurant.calculate_item_price('HAMBURGERHELLO',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_extra_2(self):
        actual = restaurant.calculate_item_price('HELLOHAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_extra_3(self):
        actual = restaurant.calculate_item_price(' HAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_extra_4(self):
        actual = restaurant.calculate_item_price('HAMBURGER ',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_partial(self):
        actual = restaurant.calculate_item_price('HAMBUR',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_empty(self):
        actual = restaurant.calculate_item_price('',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_price_random(self):
        actual = restaurant.calculate_item_price('HELLO',1)
        expected = 0
        self.assertEqual(actual, expected)

#4        # calculate_item_cost Tests!!!

    def test_calculate_item_cost_neg(self):
        actual = restaurant.calculate_item_cost('HAMBURGER',-2)
        expected = 0.0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_ZERO(self):
        actual = restaurant.calculate_item_cost('HAMBURGER',0)
        expected = 0.0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_HBone(self):
        actual = restaurant.calculate_item_cost('HAMBURGER',1)
        expected = 3.5
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_HBtwo(self):
        actual = restaurant.calculate_item_cost('HAMBURGER',2)
        expected = 7
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_HBthree(self):
        actual = restaurant.calculate_item_cost('HAMBURGER',3)
        expected = 10.5
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_HBbig(self):
        actual = restaurant.calculate_item_cost('HAMBURGER',12)
        expected = 42
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_HDone(self):
        actual = restaurant.calculate_item_cost('HOT DOG',1)
        expected = 2.5
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_HDtwo(self):
        actual = restaurant.calculate_item_cost('HOT DOG',2)
        expected = 5
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_HDthree(self):
        actual = restaurant.calculate_item_cost('HOT DOG',3)
        expected = 7.5
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_HDbig(self):
        actual = restaurant.calculate_item_cost('HOT DOG',12)
        expected = 30
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_Fone(self):
        actual = restaurant.calculate_item_cost('FRIES',1)
        expected = 3
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_Ftwo(self):
        actual = restaurant.calculate_item_cost('FRIES',2)
        expected = 6
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_Fthree(self):
        actual = restaurant.calculate_item_cost('FRIES',3)
        expected = 9
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_Fbig(self):
        actual = restaurant.calculate_item_cost('FRIES',12)
        expected = 36
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_Sone(self):
        actual = restaurant.calculate_item_cost('SODA',1)
        expected = 1
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_Stwo(self):
        actual = restaurant.calculate_item_cost('SODA',2)
        expected = 2
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_Sthree(self):
        actual = restaurant.calculate_item_cost('SODA',3)
        expected = 3
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_Sbig(self):
        actual = restaurant.calculate_item_cost('SODA',12)
        expected = 12
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_big(self):
        actual = restaurant.calculate_item_cost('HAMBURGER',100)
        expected = 350
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_case_1(self):
        actual = restaurant.calculate_item_cost('hamburger', 1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_cost_2(self):
        actual = restaurant.calculate_item_cost('Hamburger',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_3(self):
        actual = restaurant.calculate_item_cost('HAMBURGeR',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_case_4(self):
        actual = restaurant.calculate_item_cost('hamBurger',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_double(self):
        actual = restaurant.calculate_item_cost('HAMBURGERHAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_sep(self):
        actual = restaurant.calculate_item_cost('HOTDOG',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_extra_1(self):
        actual = restaurant.calculate_item_cost('HAMBURGERHELLO',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_extra_2(self):
        actual = restaurant.calculate_item_cost('HELLOHAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_extra_3(self):
        actual = restaurant.calculate_item_cost(' HAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_extra_4(self):
        actual = restaurant.calculate_item_cost('HAMBURGER ',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_partial(self):
        actual = restaurant.calculate_item_cost('HAMBUR',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_empty(self):
        actual = restaurant.calculate_item_cost('',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_item_cost_random(self):
        actual = restaurant.calculate_item_cost('HELLO',1)
        expected = 0
        self.assertEqual(actual, expected)

#5        # calculate combo price tests!!!

    def test_calculate_combo_price_neg(self):
        actual = restaurant.calculate_combo_price('HAMBURGER',-2)
        expected = 0.0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_ZERO(self):
        actual = restaurant.calculate_combo_price('HAMBURGER',0)
        expected = 0.0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_HBone(self):
        actual = restaurant.calculate_combo_price('HAMBURGER',1)
        expected = 26
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_HBtwo(self):
        actual = restaurant.calculate_combo_price('HAMBURGER',2)
        expected = 52
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_HBthree(self):
        actual = restaurant.calculate_combo_price('HAMBURGER',3)
        expected = 78
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_HBbig(self):
        actual = restaurant.calculate_combo_price('HAMBURGER',12)
        expected = 312
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_HDone(self):
        actual = restaurant.calculate_combo_price('HOT DOG',1)
        expected = 19
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_HDtwo(self):
        actual = restaurant.calculate_combo_price('HOT DOG',2)
        expected = 38
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_HDthree(self):
        actual = restaurant.calculate_combo_price('HOT DOG',3)
        expected = 57
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_HDbig(self):
        actual = restaurant.calculate_combo_price('HOT DOG',12)
        expected = 228
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_Fone(self):
        actual = restaurant.calculate_combo_price('FRIES',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_Sone(self):
        actual = restaurant.calculate_combo_price('SODA',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_big(self):
        actual = restaurant.calculate_combo_price('HAMBURGER',100)
        expected = 2600
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_case_1(self):
        actual = restaurant.calculate_combo_price('hamburger', 1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_case_2(self):
        actual = restaurant.calculate_combo_price('Hamburger',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_3(self):
        actual = restaurant.calculate_combo_price('HAMBURGeR',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_case_4(self):
        actual = restaurant.calculate_combo_price('hamBurger',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_double(self):
        actual = restaurant.calculate_combo_price('HAMBURGERHAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_sep(self):
        actual = restaurant.calculate_combo_price('HOTDOG',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_extra_1(self):
        actual = restaurant.calculate_combo_price('HAMBURGERHELLO',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_extra_2(self):
        actual = restaurant.calculate_combo_price('HELLOHAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_extra_3(self):
        actual = restaurant.calculate_combo_price(' HAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_extra_4(self):
        actual = restaurant.calculate_combo_price('HAMBURGER ',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_partial(self):
        actual = restaurant.calculate_combo_price('HAMBUR',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_empty(self):
        actual = restaurant.calculate_combo_price('',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_price_random(self):
        actual = restaurant.calculate_combo_price('HELLO',1)
        expected = 0
        self.assertEqual(actual, expected)

#6        # calculate combo cost tests!!!

    def test_calculate_combo_cost_neg(self):
        actual = restaurant.calculate_combo_cost('HAMBURGER',-2)
        expected = 0.0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_ZERO(self):
        actual = restaurant.calculate_combo_cost('HAMBURGER',0)
        expected = 0.0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_HBone(self):
        actual = restaurant.calculate_combo_cost('HAMBURGER',1)
        expected = 7.5
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_HBtwo(self):
        actual = restaurant.calculate_combo_cost('HAMBURGER',2)
        expected = 15
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_HBthree(self):
        actual = restaurant.calculate_combo_cost('HAMBURGER',3)
        expected = 22.5
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_HBbig(self):
        actual = restaurant.calculate_combo_cost('HAMBURGER',12)
        expected = 90
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_HDone(self):
        actual = restaurant.calculate_combo_cost('HOT DOG',1)
        expected = 6.5
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_HDtwo(self):
        actual = restaurant.calculate_combo_cost('HOT DOG',2)
        expected = 13
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_HDthree(self):
        actual = restaurant.calculate_combo_cost('HOT DOG',3)
        expected = 19.5
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_HDbig(self):
        actual = restaurant.calculate_combo_cost('HOT DOG',12)
        expected = 78
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_Fone(self):
        actual = restaurant.calculate_combo_cost('FRIES',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_Sone(self):
        actual = restaurant.calculate_combo_cost('SODA',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_big(self):
        actual = restaurant.calculate_combo_cost('HAMBURGER',100)
        expected = 750
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_case_1(self):
        actual = restaurant.calculate_combo_cost('hamburger', 1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_case_2(self):
        actual = restaurant.calculate_combo_cost('Hamburger',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_3(self):
        actual = restaurant.calculate_combo_cost('HAMBURGeR',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_case_4(self):
        actual = restaurant.calculate_combo_cost('hamBurger',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_double(self):
        actual = restaurant.calculate_combo_cost('HAMBURGERHAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_sep(self):
        actual = restaurant.calculate_combo_cost('HOTDOG',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_extra_1(self):
        actual = restaurant.calculate_combo_cost('HAMBURGERHELLO',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_extra_2(self):
        actual = restaurant.calculate_combo_cost('HELLOHAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_extra_3(self):
        actual = restaurant.calculate_combo_cost(' HAMBURGER',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_extra_4(self):
        actual = restaurant.calculate_combo_cost('HAMBURGER ',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_partial(self):
        actual = restaurant.calculate_combo_cost('HAMBUR',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_empty(self):
        actual = restaurant.calculate_combo_cost('',1)
        expected = 0
        self.assertEqual(actual, expected)

    def test_calculate_combo_cost_random(self):
        actual = restaurant.calculate_combo_cost('HELLO',1)
        expected = 0
        self.assertEqual(actual, expected)

#7        get item from sentences tests!!!

    def test_get_item_from_sentence_HB_one(self):
        actual = restaurant.get_item_from_sentence('Please give me a HAMBURGER.')
        expected = 'HAMBURGER'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_HB_two(self):
        actual = restaurant.get_item_from_sentence('Can I have a HAMBURGER?')
        expected = 'HAMBURGER'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_HD_one(self):
        actual = restaurant.get_item_from_sentence('Please give me a HOT DOG.')
        expected = 'HOT DOG'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_HD_two(self):
        actual = restaurant.get_item_from_sentence('Can I have a HOT DOG?')
        expected = 'HOT DOG'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_F_one(self):
        actual = restaurant.get_item_from_sentence('Please give me a FRIES.')
        expected = 'FRIES'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_F_two(self):
        actual = restaurant.get_item_from_sentence('Can I have a FRIES?')
        expected = 'FRIES'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_S_one(self):
        actual = restaurant.get_item_from_sentence('Please give me a SODA.')
        expected = 'SODA'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_S_two(self):
        actual = restaurant.get_item_from_sentence('Can I have a SODA?')
        expected = 'SODA'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_HBC_one(self):
        actual = restaurant.get_item_from_sentence('Please give me a combo of HAMBURGER.')
        expected = 'COMBO HAMBURGER'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_CHB_two(self):
        actual = restaurant.get_item_from_sentence('Can I have a HAMBURGER combo?')
        expected = 'COMBO HAMBURGER'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_CHD_one(self):
        actual = restaurant.get_item_from_sentence('Please give me a combo of HOT DOG.')
        expected = 'COMBO HOT DOG'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_CHD_two(self):
        actual = restaurant.get_item_from_sentence('Can I have a HOT DOG combo?')
        expected = 'COMBO HOT DOG'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_case_1(self):
        actual = restaurant.get_item_from_sentence('Please give me a hamburger.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_case_2(self):
        actual = restaurant.get_item_from_sentence('Can I have a HAMBURGEr?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_case_3(self):
        actual = restaurant.get_item_from_sentence('Please give me a Hamburger.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_case_4(self):
        actual = restaurant.get_item_from_sentence('Can I have a HAMBuRGER?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_case_5(self):
        actual = restaurant.get_item_from_sentence('can I have a HAMBURGER?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_case_6(self):
        actual = restaurant.get_item_from_sentence('Can i have a HAMBURGER?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_spacing_1(self):
        actual = restaurant.get_item_from_sentence(' Please give me a HAMBURGER.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_spacing_2(self):
        actual = restaurant.get_item_from_sentence('Can I have a HAMBURGER? ')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_spacing_3(self):
        actual = restaurant.get_item_from_sentence(' Please give me  a HAMBURGER.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_spacing_4(self):
        actual = restaurant.get_item_from_sentence('Can I ha ve a HAMBURGER? ')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_punct_1(self):
        actual = restaurant.get_item_from_sentence('Please give me a HAMBURGER')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_punct_2(self):
        actual = restaurant.get_item_from_sentence('Can I have a HAMBURGER')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_order_1(self):
        actual = restaurant.get_item_from_sentence('Please HAMBURGER. give a me')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_order_2(self):
        actual = restaurant.get_item_from_sentence('I a HAMBURGER? Can have')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_empty_1(self):
        actual = restaurant.get_item_from_sentence('')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_empty_2(self):
        actual = restaurant.get_item_from_sentence('Please give me a .')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_empty_3(self):
        actual = restaurant.get_item_from_sentence('Can I have a ?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_empty_4(self):
        actual = restaurant.get_item_from_sentence('Please give me a')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_empty_5(self):
        actual = restaurant.get_item_from_sentence('Can I have a')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_HBsolo(self):
        actual = restaurant.get_item_from_sentence('HAMBURGER')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_HDsolo(self):
        actual = restaurant.get_item_from_sentence('HOT DOG')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_CHBsolo(self):
        actual = restaurant.get_item_from_sentence('COMBO HAMBURGER')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_CHDsolo(self):
        actual = restaurant.get_item_from_sentence('COMBO HOT DOG')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_Fsolo(self):
        actual = restaurant.get_item_from_sentence('FRIES')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_Ssolo(self):
        actual = restaurant.get_item_from_sentence('SODA')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_FC_one(self):
        actual = restaurant.get_item_from_sentence('Please give me a combo of FRIES.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_CF_two(self):
        actual = restaurant.get_item_from_sentence('Can I have a FRIES combo?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_CS_one(self):
        actual = restaurant.get_item_from_sentence('Please give me a combo of SODA.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_CS_two(self):
        actual = restaurant.get_item_from_sentence('Can I have a SODA combo?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_extra_1(self):
        actual = restaurant.get_item_from_sentence('Please give me a HAMBURGERHELLO.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_extra_2(self):
        actual = restaurant.get_item_from_sentence('Can I have a HAMBURGER HELLO?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_extra_3(self):
        actual = restaurant.get_item_from_sentence('Please HELLO give me a HAMBURGER.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_extra_4(self):
        actual = restaurant.get_item_from_sentence('HELLO Can I have a HAMBURGER?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_wrong_1(self):
        actual = restaurant.get_item_from_sentence('Please give me a PIZZA.')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

    def test_get_item_from_sentence_wrong_2(self):
        actual = restaurant.get_item_from_sentence('Can I have a PIZZA?')
        expected = 'UNKNOWN'
        self.assertEqual(actual, expected)

if __name__ == '__main__':
    unittest.main()
