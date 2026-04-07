"""CSCA08: Functions for Assignment 3 - OpenFlights.

Instructions (READ THIS FIRST!)
===============================

Make sure that all the assignment files (flight_program.py, flight_reader.py, etc.)
are in the same directory as this file.

This file contains the starter code for getting information about airport and flight data.

Copyright and Usage Information
===============================

This code is provided solely for the personal and private use of students
taking the CSCA08 course at the University of Toronto. Copying for purposes
other than this use is expressly prohibited. All forms of distribution of
this code, whether as given or with any changes, are expressly prohibited.

All of the files in this directory and all subdirectories are:
Copyright (c) 2021 Mario Badr, Tom Fairgrieve, Amanjit Kainth, Kaveh Mahdaviani,
Sadia Sharmin, Jarrod Servilla, and Joseph Jay Williams
"""

from typing import Dict, List, Set, Tuple
from flight_types_constants_and_test_data import (
    AIRPORT_DATA_INDEXES,
    ROUTE_DATA_INDEXES,
    FLIGHT_DATA_INDEXES,
    AirportDict,
    RouteDict,
    FlightDir,
)


def get_airport_info(airports: AirportDict, iata: str, info: str) -> str:
    """Return the airport information for airport with IATA code iata for
    column info from AIRPORT_DATA_INDEXES.

    >>> get_airport_info(TEST_AIRPORTS_DICT, 'AA1', 'Name')
    'Apt1'
    >>> get_airport_info(TEST_AIRPORTS_DICT, 'AA4', 'IATA')
    'AA4'
    """

    return airports[iata][AIRPORT_DATA_INDEXES[info]]


def is_direct_flight(iata_src: str, iata_dst: str, routes: RouteDict) -> bool:
    """Return whether there is a direct flight from the iata_src airport to
    the iata_dst airport in the routes dictionary. iata_src may not
    be a key in the routes dictionary.

    >>> is_direct_flight('AA1', 'AA2', TEST_ROUTES_DICT_FOUR_CITIES)
    True
    >>> is_direct_flight('AA2', 'AA1', TEST_ROUTES_DICT_FOUR_CITIES)
    False
    """

    return iata_dst in routes[iata_src]


def is_valid_flight_sequence(iata_list: List[str], routes: RouteDict) -> bool:
    """Return whether there are flights from iata_list[i] to iata_list[i + 1]
    for all valid values of i. IATA entries may not appear anywhere in routes.

    >>> is_valid_flight_sequence(['AA3', 'AA1', 'AA2'], TEST_ROUTES_DICT_FOUR_CITIES)
    True
    >>> is_valid_flight_sequence(['AA3', 'AA1', 'AA2', 'AA1', 'AA2'], TEST_ROUTES_DICT_FOUR_CITIES)
    False
    """

    if len(iata_list) == 1:
        return True
    
    for i in range(len(iata_list)-1):
        if iata_list[i + 1] not in routes[iata_list[i]] or iata_list[i] not in routes:
            return False
        
    return True
        


def count_outgoing_flights(iata: str, routes: Routedict) -> int:
    """Retun the number of outgoing flights for the airport with the specific iata in \ 
    the given routes information.
    
    
    >>> count_outgoing_flights ('AA2', TEST_ROUTES_DICT_FOUR_CITIES)
    2
    >>> count_outgoing_flights ('AA1', TEST_ROUTES_DICT_FOUR_CITIES)
    1
    """
    
    return len(routes[iata])

def count_incoming_flights(iata: str, routes: RouteDict) -> int:
    """ Return the number of incoming flights to the airport with iata in\
    the given routes information.
   
    >>> count_incoming_flights('AA2', TEST_ROUTES_DICT_FOUR_CTIES)
    1
    >>> count_incoming_flights('AA1', TEST_ROUTES_DICT_FOUR_CTIES)
    2
    
    """
    

def count_total_flights(iata: str, routes: routeDict) -> int:
    
    """Return the total number of flights that are present at iata.
    
    >>> count_total_flights('AA2', TEST_ROUTES_DICT_FOUR_CTIES)
    2
    >>> count_total_flights('AA1', TEST_ROUTES_DICT_FOUR_CTIES)
    4
    
    """
    if iata not in routes:
        return 0
    return count_outgoing_flights(iata, routes) + count_incoming_flights(iata, routes)


def reachable_destinations(iata_src: str, n: int, routes: RouteDict) -> List[Set[str]]:
    """Return a list of the sets of airports where the set at index i is
    reachable in at most i flights. Note that iata_src will always appear at
    index 0, because it is reachable without flying anywhere.

    Precondition: n >= 0

    >>> reachable_destinations('AA1', 0, TEST_ROUTES_DICT_FOUR_CITIES)
    [{'AA1'}]
    >>> expected = [{'AA1'}, {'AA2', 'AA4'}]
    >>> result = reachable_destinations('AA1', 1, TEST_ROUTES_DICT_FOUR_CITIES)
    >>> expected == result
    True
    >>> expected = [{'AA1'}, {'AA2', 'AA4'}, {'AA3'}]
    >>> result = reachable_destinations('AA1', 2, TEST_ROUTES_DICT_FOUR_CITIES)
    >>> expected == result
    True
    """

    if n == 0:
        return [{iata_src}]
    elif n == 1:
        return get_destination(iata_src, 1, routes)
    else:
        reachable_list = [{iata_src}]
        get_list = get_destination(iata_src, n, routes)
        for i_2 in range(1, len(get_list)):
            for i_3 in reachable_list[:i_2]:
                a = get_list[i_2] - i_3
                b = a
                get_list[i_2] = b
                if b != set() and b not in reachable_list:
                    reachable_list.append(b)
                    
        return reachable_list

    
def calculate_trip_time(iata_src: str, iata_dst: str, flight_walk: List[str], flights: FlightDir) -> float:
    """ Return a float corresponding to the amount of time required to travel 
    from the source airport <iata_src> to the destination airport <iata_dst> to 
    the destination airport, as outlined by the flight_walk. 

    The start time of the trip should be considered zero. In other words, 
    assuming we start the trip at 12:00am , this function should return the time
    it takes for the trip to finish, including all the waiting times before, and
    between the flights.

    If there is no path available, return -1.0
    
    >>> calculate_trip_time("AA1", "AA2", ["AA1", "AA2"], TEST_FLIGHTS_DIR_FOUR_CITIES)
    2.0
    >>> calculate_trip_time("AA1", "AA7", ["AA7", "AA1"], TEST_FLIGHTS_DIR_FOUR_CITIES)
    -1.0
    >>> calculate_trip_time("AA1", "AA7", ["AA1", "AA7"], TEST_FLIGHTS_DIR_FOUR_CITIES)
    -1.0
    >>> calculate_trip_time("AA1", "AA1", ["AA1"], TEST_FLIGHTS_DIR_FOUR_CITIES)
    0.0
    >>> calculate_trip_time("AA4", "AA2", ["AA4", "AA1", "AA2"], TEST_FLIGHTS_DIR_FOUR_CITIES)
    14.0
    >>> calculate_trip_time("AA1", "AA3", ["AA1", "AA2", "AA3"], TEST_FLIGHTS_DIR_FOUR_CITIES)
    7.5
    >>> calculate_trip_time("AA1", "AA4", ["AA1", "AA4"], TEST_FLIGHTS_DIR_FOUR_CITIES)
    2.0
    """

    flight_schedule = {}
    for flight in flights.flights:
        src, dst, duration = flight
        if src not in flight_schedule:
            flight_schedule[src] = []
        flight_schedule[src].append((dst, duration))

    arrival_times = {iata_src: 0.0}

    taken_flights = [iata_src]

    for i in range(1, len(flight_walk)):
        src = flight_walk[i - 1]
        dst = flight_walk[i]
    if src not in flight_schedule or dst not in [flight[0] for flight in flight_schedule[sc]]:
        return -1.0 
    duration = [flight[1] for flight in flight_schedule[src] if flight [0] == dst][0]
    arrival_time = arrival_times[src] + duration
    if dst in arrival_times and arrival_time < arrival_times [dst]:
        arrival_time = arrival_times[dst]
    arrival_times[dst] = arrival_time
    taken_flights.append(dst)


trip_time = arrival_times[iata_dst] - arrival_times[iata_src]

return trip_time


if __name__ == "__main__":
    """Uncommment the following as needed to run your doctests"""
    # from flight_types_constants_and_test_data import TEST_AIRPORTS_DICT
    # from flight_types_constants_and_test_data import TEST_AIRPORTS_SRC
    # from flight_types_constants_and_test_data import TEST_ROUTES_DICT_FOUR_CITIES
    # from flight_types_constants_and_test_data import TEST_ROUTES_SRC
    # from flight_types_constants_and_test_data import TEST_FLIGHTS_DIR_FOUR_CITIES
    # from flight_types_constants_and_test_data import TEST_FLIGHTS_SRC

    # import doctest
    # doctest.testmod()
