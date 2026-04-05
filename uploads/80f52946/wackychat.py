"""
CSCA08: Winter 2024 -- Assignment 3: WackyChat

This code is provided solely for the personal and private use of
students taking the CSCA08 course at the University of
Toronto. Copying for purposes other than this use is expressly
prohibited. All forms of distribution of this code, whether as given
or with any changes, are expressly prohibited.
"""

from typing import TextIO
from datetime import datetime
import tempfile
import os

# This is an example of what the contents of a file might look like.
SAMPLE_TEXT_CONTEXT_1 = """
GROUP
9119
CSCA08
CHANNEL
48805
9119
Irene's Classroom
CHANNEL
6265
9119
Purva's Classroom
MESSAGE
12255
48805
2024/11/16 23:32:52
Charles Xu
I am working on CSCA08 Assignment 3!
DONE
"""

SAMPLE_TEXT_CONTEXT_2 = """
GROUP
9119
CSCA08
CHANNEL
6265
9119
Purva's Classroom
CHANNEL
48805
9119
Irene's Classroom
MESSAGE
12255
48805
2024/11/16 23:32:52
Charles Xu
I am working on CSCA08 Assignment 3!
DONE
"""

# This is the translation of the above contents as a series of dicts & arrays.
SAMPLE_DICT_CONTEXT_1 = {
    "groups": [{
        "id": 9119,
        "name": "CSCA08"
    }],
    "channels": [{
        "id": 48805,
        "group": 9119,
        "name": "Irene's Classroom"
    }, {
        "id": 6265,
        "group": 9119,
        "name": "Purva's Classroom"
    }],
    "messages": [{
        "id": 12255,
        "channel": 48805,
        "time": "2024/11/16 23:32:52",
        "name": "Charles Xu",
        "message": "I am working on CSCA08 Assignment 3!"
    }]
}

SAMPLE_DICT_CONTEXT_2 = {
    "groups": [{
        "id": 9119,
        "name": "CSCA08"
    }],
    "channels": [{
        "id": 6265,
        "group": 9119,
        "name": "Purva's Classroom"
    }, {
        "id": 48805,
        "group": 9119,
        "name": "Irene's Classroom"
    }],
    "messages": [{
        "id": 12255,
        "channel": 48805,
        "time": "2024/11/16 23:32:52",
        "name": "Charles Xu",
        "message": "I am working on CSCA08 Assignment 3!"
    }]
}


def is_valid_date(date: str) -> bool:
    '''
    Returns True if and only if the given string 'date' is valid and in the
    format of 'year/month/day hour:minute:second'.

    >>> is_valid_date('2024/11/16 23:32:52')
    True
    >>> is_valid_date('2024/13/13 25:25:25')
    False
    >>> is_valid_date('Banana')
    False
    '''
    try:
        datetime.strptime(date, '%Y/%m/%d %H:%M:%S')
        return True
    except ValueError:
        return False


def create_temporary_file() -> str:
    '''
    Create a temporary file inside the system's temporary directory and return
    its absolute path.

    >>> file_path = create_temporary_file()
    >>> os.path.exists(file_path)
    True
    >>> os.remove(file_path)
    >>> os.path.exists(file_path)
    False
    '''
    return tempfile.NamedTemporaryFile(delete=False).name


def create_group(context: dict, group_id: int, name: str) -> bool:
    '''
    Returns True if and only if a new group is successfully
    added to 'context' with the id 'group_id' and the
    name 'name'.

    >>> create_group({}, 'abc', 'Group 1')
    True
    >>> create_group({'channels': []}, 'abc', 'Group 1')
    True
    >>> create_group({'groups': []}, 'abc', 'Group 1')
    True
    >>> create_group({'groups': [{'id': 'abc', 'name': 'Group 1'}]},
    ... 'abc', 'Group 1')
    False
    >>> create_group({'groups': [{'id': 'abc', 'name': 'Group 2'}]},
    ... 'abc', 'Group 1')
    False
    >>> create_group({'groups': [{'id': 'def', 'name': 'Group 1'}]},
    ... 'abc', 'Group 1')
    True
    >>> create_group({'groups': [{'id': 'def', 'name': 'Group 2'}]},
    ... 'abc', 'Group 1')
    True
    '''
    if 'groups' in context:
        for group in context['groups']:
            if group['id'] == group_id:
                return False
    else:
        context['groups'] = []
    context['groups'].append({'id': group_id, 'name': name})
    return True


def create_channel(context: dict, group_id: int, channel_id: int,
                   name: str) -> bool:
    '''
    Returns True if and only if a new channel is successfully
    added to 'context' with the id 'channel_id', group 'group_id'
    and the name 'name'.

    >>> create_channel({}, 'g1', 'c1', 'Name')
    False
    >>> create_channel({'groups': []}, 'g1', 'c1', 'Name')
    False
    >>> create_channel({'groups': [{'id': 'g2', 'name': 'Group'}]},
    ... 'g1', 'c1', 'Name')
    False
    >>> create_channel({'groups': [{'id': 'g1', 'name': 'Group'}]},
    ... 'g1', 'c1', 'Name')
    True
    >>> create_channel({'groups': [], 'channels': []}, 'g1', 'c1', 'Name')
    False
    >>> create_channel({'groups': [{'id': 'g2', 'name': 'Group'}],
    ... 'channels': []}, 'g1', 'c1', 'Name')
    False
    >>> create_channel({'groups': [{'id': 'g1', 'name': 'Group'}],
    ... 'channels': []}, 'g1', 'c1', 'Name')
    True
    >>> create_channel({'groups': [{'id': 'g1', 'name': 'Group'}],
    ... 'channels': [{'id': 'c1', 'group': 'g1', 'name': 'Channel'}]},
    ... 'g1', 'c1', 'Name')
    False
    >>> create_channel({'groups': [{'id': 'g1', 'name': 'Group'}],
    ... 'channels': [{'id': 'c1', 'group': 'g2', 'name': 'Channel'}]},
    ... 'g1', 'c1', 'Name')
    False
    >>> create_channel({'groups': [{'id': 'g1', 'name': 'Group'}],
    ... 'channels': [{'id': 'c2', 'group': 'g2', 'name': 'Channel'}]},
    ... 'g1', 'c1', 'Name')
    True
    '''
    if 'channels' in context:
        for channel in context['channels']:
            if channel['id'] == channel_id:
                return False
    if not 'groups' in context:
        return False
    for group in context['groups']:
        if group['id'] == group_id:
            break
    else:
        return False
    if not 'channels' in context:
        context['channels'] = []
    new_channel = {'id': channel_id, 'group':  group_id, 'name': name}
    context['channels'].append(new_channel)
    return True


def send_message(context: dict, channel_id: int, message_id: int,
                 time: str, name: str, message: str) -> bool:
    '''
    invalid channel
    invalid date
    invalid time
    duplicate message id
    empty context
    same message, different id
    '''
    if 'messages' in context:
        for message_object in context['messages']:
            if message_object['id'] == message_id:
                return False
    if not 'channels' in context:
        return False
    for channel in context['channels']:
        if channel['id'] == channel_id:
            break
    else:
        return False
    if not is_valid_date(time):
        return False
    if not 'messages' in context:
        context['messages'] = []
    new_message = {'id': message_id, 'channel': channel_id,
    'time': time, 'name': name, 'message': message}
    context['messages'].append(new_message)
    return True


def read_context_from_file(file_io: TextIO) -> dict | None:
    '''
    TODO: Complete this function and its docstring.

    >>> file_path = create_temporary_file()
    >>> file = open(file_path, "w")
    >>> index = file.write(SAMPLE_TEXT_CONTEXT_1)
    >>> file.close()
    >>> file = open(file_path, "r")
    >>> context = read_context_from_file(file)
    >>> file.close()
    >>> context == SAMPLE_DICT_CONTEXT_1
    True
    >>> file_path = create_temporary_file()
    >>> file = open(file_path, "w")
    >>> index = file.write(SAMPLE_TEXT_CONTEXT_2)
    >>> file.close()
    >>> file = open(file_path, "r")
    >>> context = read_context_from_file(file)
    >>> file.close()
    >>> context == SAMPLE_DICT_CONTEXT_2
    True
    '''
    context = {}
    groups = []
    channels = []
    messages = []
    line = file_io.readline().strip()
    while not line == "DONE":
        if line == "GROUP":
            group_id = int(file_io.readline().strip())
            name = file_io.readline().strip()
            groups.append([group_id, name])
        if line == "CHANNEL":
            channel_id = int(file_io.readline().strip())
            group = int(file_io.readline().strip())
            name = file_io.readline().strip()
            channels.append([group, channel_id, name])
        if line == "MESSAGE":
            message_id = int(file_io.readline().strip())
            channel = int(file_io.readline().strip())
            time = file_io.readline().strip()
            name = file_io.readline().strip()
            msg = file_io.readline().strip()
            messages.append([channel, message_id, time, name, msg])
        line = file_io.readline().strip()
    for group in groups:
        if not create_group(context, *group):
            return None
    for channel in channels:
        if not create_channel(context, *channel):
            return None
    for message in messages:
        if not send_message(context, *message):
            return None
    return context


def get_user_word_frequency(context: dict, name: str) -> dict:
    '''
    Returns a dictionary, mapping every word the user 'name' has
    used to the number of times they have used that word in all of
    their messages in 'context'.
    >>> get_user_word_frequency({}, "A")
    {}
    >>> get_user_word_frequency({'groups': [], 'channels': [],
    ... 'messages': []}, "A")
    {}
    >>> get_user_word_frequency({
    ... "groups": [{
    ...     "id": 9119,
    ...     "name": "CSCA08"
    ... }],
    ... "channels": [{
    ...     "id": 48805,
    ...     "group": 9119,
    ...     "name": "Irene's Classroom"
    ... }],
    ... "messages": [{
    ...     "id": 12255,
    ...     "channel": 48805,
    ...     "time": "2024/11/16 23:32:52",
    ...     "name": "Charles Xu",
    ...     "message": "I am working on CSCA08 Assignment 3!"
    ... }]
    ... }, "A")
    {}
    >>> result = {'I': 1, 'am': 1, 'working': 1, 'on': 1, 'CSCA08': 1,
    ... 'Assignment': 1, '3!': 1}
    >>> result == get_user_word_frequency({
    ... "groups": [{
    ...     "id": 9119,
    ...     "name": "CSCA08"
    ... }],
    ... "channels": [{
    ...     "id": 48805,
    ...     "group": 9119,
    ...     "name": "Irene's Classroom"
    ... }],
    ... "messages": [{
    ...     "id": 12255,
    ...     "channel": 48805,
    ...     "time": "2024/11/16 23:32:52",
    ...     "name": "Charles Xu",
    ...     "message": "I am working on CSCA08 Assignment 3!"
    ... }]
    ... }, "Charles Xu")
    True
    >>> get_user_word_frequency({
    ... "groups": [{
    ...     "id": 9119,
    ...     "name": "CSCA08"
    ... }],
    ... "channels": [{
    ...     "id": 48805,
    ...     "group": 9119,
    ...     "name": "Irene's Classroom"
    ... }],
    ... "messages": [{
    ...     "id": 12255,
    ...     "channel": 48805,
    ...     "time": "2024/11/16 23:32:52",
    ...     "name": "Charles Xu",
    ...     "message": "One two three"
    ... }, {
    ...     "id": 12256,
    ...     "channel": 48805,
    ...     "time": "2024/11/16 23:32:52",
    ...     "name": "Charlie Apple Sauce",
    ...     "message": "One two three four"
    ... }]
    ... }, "Charles Xu")
    {'One': 1, 'two': 1, 'three': 1}
    >>> get_user_word_frequency({
    ... "groups": [{
    ...     "id": 9119,
    ...     "name": "CSCA08"
    ... }],
    ... "channels": [{
    ...     "id": 48805,
    ...     "group": 9119,
    ...     "name": "Irene's Classroom"
    ... }],
    ... "messages": [{
    ...     "id": 12255,
    ...     "channel": 48805,
    ...     "time": "2024/11/16 23:32:52",
    ...     "name": "Charles Xu",
    ...     "message": "One two three"
    ... }, {
    ...     "id": 12256,
    ...     "channel": 48805,
    ...     "time": "2024/11/16 23:32:52",
    ...     "name": "Charles Xu",
    ...     "message": "One two three four"
    ... }]
    ... }, "Charles Xu")
    {'One': 2, 'two': 2, 'three': 2, 'four': 1}
    '''
    if not 'messages' in context:
        return {}
    return_dict = {}
    for message in context['messages']:
        if message['name'] == name:
            words = message['message'].strip().split()
            for word in words:
                if word in return_dict:
                    return_dict[word] += 1
                else:
                    return_dict[word] = 1
    return return_dict


def get_user_character_frequency_percentage(context: dict, name: str) -> dict:
    '''
    TODO: Complete this function and its docstring.
    >>> result = {'I': 0.027777777777777776,
    ... ' ': 0.16666666666666666, 'a': 0.027777777777777776,
    ... 'm': 0.05555555555555555, 'w': 0.027777777777777776,
    ... 'o': 0.05555555555555555, 'r': 0.027777777777777776,
    ... 'k': 0.027777777777777776, 'i': 0.05555555555555555,
    ... 'n': 0.1111111111111111, 'g': 0.05555555555555555,
    ... 'C': 0.05555555555555555, 'S': 0.027777777777777776,
    ... 'A': 0.05555555555555555, '0': 0.027777777777777776,
    ... '8': 0.027777777777777776, 's': 0.05555555555555555,
    ... 'e': 0.027777777777777776, 't': 0.027777777777777776,
    ... '3': 0.027777777777777776, '!': 0.027777777777777776}
    >>> get_user_character_frequency_percentage(
    ... SAMPLE_DICT_CONTEXT_1, 'Charles Xu') == result
    True
    >>> result = {}
    >>> get_user_character_frequency_percentage(
    ... SAMPLE_DICT_CONTEXT_1, 'Mr. Nobody') == result
    True
    '''
    if not 'messages' in context:
        return {}
    return_dict = {}
    total = 0
    for message in context['messages']:
        if not message['name'] == name:
            continue
        for character in message['message']:
            total += 1
            if character in return_dict:
                return_dict[character] += 1
            else:
                return_dict[character] = 1
    for key in return_dict:
        return_dict[key] /= total
    return return_dict



def get_most_popular_group(context: dict) -> int | None:
    '''
    Returns the id of the group with the most number of messages.
    If there are no groups, returns None. If there are multiple
    groups with the same number of messages, return the
    group with the smallest id.
    >>> get_most_popular_group({}) == None
    True
    >>> get_most_popular_group({'groups': []}) == None
    True
    >>> get_most_popular_group(SAMPLE_DICT_CONTEXT_1) == 9119
    True
    '''
    if not 'messages' in context or context['messages'] == []:
        if not 'groups' in context or context['groups'] == []:
            return None
        return min(group["id"] for group in context['groups'])
    channel_to_group = {}
    group_to_tally = {}
    for channel in context['channels']:
        channel_to_group[channel['id']] = channel['group']
    for message in context['messages']:
        key = channel_to_group[message['channel']]
        if key in group_to_tally:
            group_to_tally[key] += 1
        else:
            group_to_tally[key] = 1
    key = list(group_to_tally.keys())[0]
    for current_object in group_to_tally.items():
        if current_object[1] > group_to_tally[key]:
            key = current_object[0]
        elif current_object[1] == group_to_tally[key]:
            key = min(key, current_object[0])
    return key


if __name__ == '__main__':
    import doctest
    doctest.testmod()
