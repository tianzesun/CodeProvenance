"""CSCA08: Fall 2022 -- Assignment 3: Hypertension and Low Income

Starter code.

This code is provided solely for the personal and private use of
students taking the CSC108/CSCA08 course at the University of
Toronto. Copying for purposes other than this use is expressly
prohibited. All forms of distribution of this code, whether as given
or with any changes, are expressly prohibited.

All of the files in this directory and all subdirectories are:
Copyright (c) 2022 Jacqueline Smith, David Liu, and Anya Tafliovich

"""

from typing import TextIO
import statistics

from constants import (CityData, ID, HT, TOTAL, LOW_INCOME,
                       SEP, HT_ID_COL, LI_ID_COL,
                       HT_NBH_NAME_COL, LI_NBH_NAME_COL,
                       HT_20_44_COL, NBH_20_44_COL,
                       HT_45_64_COL, NBH_45_64_COL,
                       HT_65_UP_COL, NBH_65_UP_COL,
                       POP_COL, LI_POP_COL,
                       HT_20_44_IDX, HT_45_64_IDX, HT_65_UP_IDX,
                       NBH_20_44_IDX, NBH_45_64_IDX, NBH_65_UP_IDX
                       )
SAMPLE_DATA = {
    'West Humber-Clairville': {
        'id': 1,
        'hypertension': [703, 13291, 3741, 9663, 3959, 5176],
        'total': 33230, 'low_income': 5950},
    'Mount Olive-Silverstone-Jamestown': {
        'id': 2,
        'hypertension': [789, 12906, 3578, 8815, 2927, 3902],
        'total': 32940, 'low_income': 9690},
    'Thistletown-Beaumond Heights': {
        'id': 3,
        'hypertension': [220, 3631, 1047, 2829, 1349, 1767],
        'total': 10365, 'low_income': 2005},
    'Rexdale-Kipling': {
        'id': 4,
        'hypertension': [201, 3669, 1134, 3229, 1393, 1854],
        'total': 10540, 'low_income': 2140},
    'Elms-Old Rexdale': {
        'id': 5,
        'hypertension': [176, 3353, 1040, 2842, 948, 1322],
        'total': 9460, 'low_income': 2315}
}
EPSILON = 0.005


def get_bigger_neighbourhood(city_data: CityData, nbh1: str, nbh2: str) -> str:
    
    """returns the name of the neighbourhood that has a higher population, 
       according to the low income data.
    >>> get_bigger_neighbourhood(SAMPLE_DATA, 'Elms-Old Rexdale', 
           'Rexdale-Kipling')
           
        'Elms-Old Rexdale'
    >>> get_bigger_neighbourhood(SAMPLE_DATA, 'West Humber-Clairville', 
        'Thistletown-Beaumond Heights')
          
        'West Humber-Clairville'
          
    """
    
    pop1 = 0
    pop2 = 0
    
    if nbh1 in city_data:
        pop1 = city_data[nbh1]['low_income']
    if nbh2 in city_data:
        pop2 = city_data[nbh2]['low_income']
    if pop1 >= pop2:
        
        return nbh1
    return nbh2

def get_high_hypertension_rate(city_data: CityData, 
                               threshold: float) -> list[tuple[str, float]]:
    
    """
    return a list of tuples representing all neighbourhoods with a hypertension 
    rate greater than or equal to the threshold. In each tuple, the first item 
    is the neighbourhood name and the second item is the hypertension rate 
    in that neighbourhood.
    
    >>> get_high_hypertension_rate(SAMPLE_DATA, 0.3)
    
        [('Thistletown-Beaumond Heights', 0.31797739151574084), 
        ('Rexdale-Kipling', 0.3117001828153565)]
        
    >>> get_high_hypertension_rate(SAMPLE_DATA, 0.5)
        
        [ ] 
        
    """
    
    results = [ ]
    
    for neighborhood, data in city_data.items():
        hypertension_rate = sum(data["hypertension"][::2]) / sum(
            data["hypertension"][1::2])
        if hypertension_rate >= threshold:
            results.append((neighborhood , hypertension_rate))
            
    return results

def get_ht_to_low_income_ratios(city_data: CityData) -> dict[str, float]:
    """returns a dictionary where the keys are the same as in the parameter, 
    and the values are the ratio of the hypertension rate to the low income 
    rate for that neighbourhood.
    
    >>> get_ht_to_low_income_ratios(SAMPLE_DATA)
    
        {'West Humber-Clairville': 1.2845836859365323, 
        'Mount Olive-Silverstone-Jamestown': 0.7532607343114887, 
        'Thistletown-Beaumond Heights': 1.247220416173437, 
        'Rexdale-Kipling': 1.170386531635677, 
        'Elms-Old Rexdale': 0.9134340092581871}
        
    """    
   
    result = {}
    
    for city in city_data:
        hypertension_rate = get_ht_rate(city_data[city]["hypertension"])
        
        low_income_rate = get_low_income_rate(city_data[city]["low_income"], 
                                              city_data[city]["total"])
        
        ht_to_low_income_ratio = hypertension_rate / low_income_rate
        
        result[city] = ht_to_low_income_ratio
        
    return result

def calculate_ht_rates_by_age_group(city_data: CityData, 
                                    nbh_name: str
                                    ) -> tuple[float, float, float]:
    
    """
    returns a tuple of three values, representing the hypertension 
    rate for each of the three age groups in the neighbourhood as a percentage
    
    >>> calculate_ht_rates_by_age_group(SAMPLE_DATA, 'Elms-Old Rexdale')
    
        (5.24903071875932, 36.593947923997185, 71.70953101361573)
        
    >>> calculate_ht_rates_by_age_group(SAMPLE_DATA, 
        'Thistletown-Beaumond Heights')
        
        (6.058936931974663, 37.009544008483566, 76.34408602150538)
        
    """
    
    nbh_hypertension = city_data[nbh_name]["hypertension"]
    rate_20_44 = (nbh_hypertension[0] / nbh_hypertension[1]) * 100
    rate_45_64 = (nbh_hypertension[2] / nbh_hypertension[3]) * 100
    rate_over_65 = (nbh_hypertension[4] / nbh_hypertension[5]) * 100
    
    return(rate_20_44, rate_45_64, rate_over_65)
    
def order_by_ht_rate(city_data: CityData) -> list[str]:
    """return a list of the names of the neighbourhoods, ordered from lowest 
    to highest age-standardised hypertension rate
    
    >>> order_by_ht_rate(SAMPLE_DATA)
        ['Elms-Old Rexdale', 'Rexdale-Kipling', 'Thistletown-Beaumond Heights', 
        'West Humber-Clairville', 'Mount Olive-Silverstone-Jamestown']
        
    >>> order_by_ht_rate(CityData)
        ['Elms-Old Rexdale', 'Rexdale-Kipling', 'Thistletown-Beaumond Heights', 
        'West Humber-Clairville', 'Mount Olive-Silverstone-Jamestown']
        
    """
    
    cities = [ ]
    
    for city, data in city_data.items():
        cities.append(city)
        city_data[city]['hypertension'] = sorted(data['hypertension'])
        
        cities = sorted(cities, key = lambda x: city_data[x]['hypertension'])
        
    return cities 

def get_correlation(city_data: CityData) -> float:

    x = [] 
    y = []
    for key in city_data:
        temp = get_age_standardized_ht_rate(city_data, key)
        x = [x, temp]
        temp = get_low_income_rate(city_data[key]['low_income'], 
                                   city_data[key]['total'])
        y = [y, temp]
    
        
    return statistics.correlation(x,y)

    
    
    
    
    



#HELPER FUNCTIONS

# This function is provided for use in Task 3. You do not need to
# change it.  Note the use of EPSILON constant (similar to what we had
# in asisgnment 2) for testing.
def get_age_standardized_ht_rate(city_data: CityData, nbh_name: str) -> float:
    """Return the age standardized hypertension rate from the
    neighbourhood in city_data with neighbourhood name nbh_name.

    Precondition: nbh_name is in city_data

    >>> abs(get_age_standardized_ht_rate(SAMPLE_DATA, 'Elms-Old Rexdale') -
    ...     24.44627) < EPSILON
    True
    >>> abs(get_age_standardized_ht_rate(SAMPLE_DATA, 'Rexdale-Kipling') -
    ...     24.72562) < EPSILON
    True

    """

    rates = calculate_ht_rates_by_age_group(city_data, nbh_name)

    # These rates are normalized for only 20+ ages, using the census data
    # that our datasets are based on.
    canada_20_44 = 11_199_830 / 19_735_665   # Number of 20-44 / Number of 20+
    canada_45_64 = 5_365_865 / 19_735_665    # Number of 45-64 / Number of 20+
    canada_65_plus = 3_169_970 / 19_735_665  # Number of 65+ / Number of 20+

    return (rates[0] * canada_20_44 + rates[1] * canada_45_64 +
            rates[2] * canada_65_plus)


def get_ht_rate(hypertension: list) -> float:
    
    """Returns the hypertension rate from int values in a list.
    
    >>> get_ht_rate([703, 13291, 3741, 9663, 3959, 5176])
    
        0.2300112227301344
        
    >>> get_ht_rate([220, 3631, 1047, 2829, 1349, 1767])
    
        0.24126164345660794
    
    """
    
    num_hypertension_people = 0 
    total_population = 0
    
    for i in range(len(hypertension)):
        if i % 2 == 0:
            num_hypertension_people += hypertension[i]
        total_population += hypertension[i]
            
    return num_hypertension_people / total_population

def get_low_income_rate(low_income: int, total: int) -> float:
    """Returns the low income rate by dividing low income by total.
    
    >>> get_low_income_rate(2140, 10540)
    
        0.2030360531309298
        
    >>> get_low_income_rate(2315, 9460)
    
        0.24471458773784355
        
    """    
    
    return low_income / total


if __name__ == '__main__':
    import doctest
    doctest.testmod()

    # Uncomment when ready to test:
    # Using the small data files:
    # small_data = {}
    # add hypertension data
    # with open('../data/hypertension_data_small.csv') as ht_small_f:
    #    get_hypertension_data(small_data, ht_small_f)
    # add low income data
    # with open('../data/low_income_small.csv') as li_small_f:
    #    get_low_income_data(small_data, li_small_f)

    # print('Did we build the dict correctly?', small_data == SAMPLE_DATA)
    # print('Correlation in small data file:', get_correlation(small_data))

    # Using the example data files:
    # example_neighbourhood_data = {}
    # add hypertension data
    # with open('../data/hypertension_data_2016.csv') as ht_example_f:
    #    get_hypertension_data(example_neighbourhood_data, ht_example_f)
    # add low income data
    # with open('../data/low_income_2016.csv') as li_example_f:
    #    get_low_income_data(example_neighbourhood_data, li_example_f)
    # print('Correlation in example data file:',
    #      get_correlation(example_neighbourhood_data))
