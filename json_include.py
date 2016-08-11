#!/usr/bin/env python
# coding: utf-8
import os
import re
import json
import random
import string
from collections import OrderedDict
import argparse

OBJECT_TYPES = (dict, list)
INCLUDE_KEY = '...'
INCLUDE_VALUE_PATTERN = re.compile(r'^include\((.+)\)$')
INCLUDE_TEXT_PATTERN = re.compile(r'^include_text\((.+)\)$')
_included_cache = {}


def random_string(N=9):
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(N))


def read_file(filepath):
    with open(filepath, 'r') as f:
        return f.read()


def get_include_name(value, regex):
    if isinstance(value, basestring):
        rv = regex.search(value)
        if rv:
            return rv.groups()[0]
    return None


def make_unique(obj, key, original=None, replacement=None):
    """
    Walk through the dict and add random string to the value at key
    and all other occurences of the same value.
    """
    if key in obj and isinstance(obj[key], basestring):
        original = obj[key]
        replacement = obj[key] + "-" + random_string()
        obj[key] = replacement
    for k, v in obj.items():
        if original and v == original:
            obj[k] = replacement
        if isinstance(v, dict):
            make_unique(v, key, original, replacement)
    return obj


def walk_through_to_include(o, dirpath):
    if isinstance(o, dict):
        is_include_exp = False
        make_unique_key = o.pop('makeUnique', None)
        if set(o) == set([INCLUDE_KEY]):
            include_name = get_include_name(o.values()[0], INCLUDE_VALUE_PATTERN)
            if include_name:
                is_include_exp = True
                o.clear()
                # enable relative directory references: `../../`
                _f = os.path.join(dirpath, include_name)
                if include_name not in _included_cache:
                    _included_cache[include_name] = parse_json_include(
                        os.path.dirname(_f), os.path.basename(_f), True)
                _data = _included_cache[include_name]
                o.update(make_unique(_data, make_unique_key) if make_unique_key else _data)

        include_text_keys = [key for key in o.keys()
                             if isinstance(o[key], basestring) and INCLUDE_TEXT_PATTERN.search(o[key])]
        for key in include_text_keys:
            include_filename = get_include_name(o[key], INCLUDE_TEXT_PATTERN)
            if include_filename:
                _f = os.path.join(dirpath, include_filename)
                with open(os.path.join(_f)) as file:
                    o[key] = file.read()

        if is_include_exp:
            return

        for k, v in o.iteritems():
            if isinstance(v, OBJECT_TYPES):
                walk_through_to_include(v, dirpath)
    elif isinstance(o, list):
        for i in o:
            if isinstance(i, OBJECT_TYPES):
                walk_through_to_include(i, dirpath)


def parse_json_include(dirpath, filename, is_include=False):
    filepath = os.path.join(dirpath, filename)
    json_str = read_file(filepath)
    d = json.loads(json_str, object_pairs_hook=OrderedDict)

    if is_include:
        assert isinstance(d, dict),\
            'The JSON file being included should always be a dict rather than a list'

    walk_through_to_include(d, dirpath)

    return d


def build_json_include(dirpath, filename, indent=4):
    """Parse a json file and build it by the include expression recursively.

    :param str dirpath: The directory path of source json files.
    :param str filename: The name of the source json file.
    :return: A json string with its include expression replaced by the indicated data.
    :rtype: str
    """
    d = parse_json_include(dirpath, filename)
    return json.dumps(d, indent=indent, separators=(',', ': '))


def build_json_include_to_files(dirpath, filenames, target_dirpath, indent=4):
    """Build a list of source json files and write the built result into
    target directory path with the same file name they have.

    Since all the included JSON will be cached in the parsing process,
    this function will be a better way to handle multiple files than build each
    file seperately.

    :param str dirpath: The directory path of source json files.
    :param list filenames: A list of source json files.
    :param str target_dirpath: The directory path you want to put built result into.
    :rtype: None
    """
    assert isinstance(filenames, list), '`filenames must be a list`'

    if not os.path.exists(target_dirpath):
        os.makedirs(target_dirpath)

    for i in filenames:
        json = build_json_include(dirpath, i, indent)
        target_filepath = os.path.join(target_dirpath, i)
        with open(target_filepath, 'w') as f:
            f.write(json)


def main():
    parser = argparse.ArgumentParser(description='Command line tool to build JSON file by include syntax.')

    parser.add_argument('dirpath', metavar="DIR", help="The directory path of source json files")
    parser.add_argument('filename', metavar="FILE", help="The name of the source json file")

    args = parser.parse_args()

    print build_json_include(args.dirpath, args.filename)


if __name__ == '__main__':
    main()
