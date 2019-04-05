import os
import re
import json
import random
import string

from collections import OrderedDict

OBJECT_TYPES = (dict, list)
INCLUDE_KEYS = ['...', '$ref']
INCLUDE_VALUE_PATTERNS = [
    re.compile(r'^#/(.+)$'),  # simple local definition
    re.compile(r'^include\((.+)\)$'),  # include
    re.compile(r'^file:(.+)?#/(.+)$'),  # remote definition inclusion
    re.compile(r'^file:(.+)$'),  # remote file inclusion
    re.compile(r'^(.+)?#/(.+)$'),  # remote definition inclusion without `file:` pattern
    re.compile(r'^(.+)$'),  # remote file inclusion without `file:` pattern (must be the last one)
]
INCLUDE_TEXT_PATTERN = re.compile(r'^include_text\((.+)\)$')


class JSONInclude(object):
    def __init__(self):
        self._included_cache = None
        self._original_schemas = None

    def _random_string(self, length=9):
        return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(length))

    def _read_file(self, filePath):
        with open(filePath) as f:
            return f.read()

    def _get_include_name(self, value, regex_list):
        if not isinstance(regex_list, list):
            # passing single regex only
            regex = regex_list
            if isinstance(value, basestring):
                rv = regex.search(value)
                if rv:
                    return rv.groups()[0]
            return None
        else:
            # passing list of regex`s
            for idx, regex in enumerate(regex_list):
                if isinstance(value, basestring):
                    rv = regex.search(value)
                    if rv:
                        return rv.groups(), idx
            return None, None

    def _lookup(self, dic, key, *keys):
        if keys:
            return self._lookup(dic.get(key, {}), *keys)
        return dic.get(key)

    def _make_unique(self, obj, key, original=None, replacement=None):
        """
        Walk through the dict and add random string to the value at key
        and all other occurrences of the same value.
        """
        if key in obj and isinstance(obj[key], basestring):
            original = obj[key]
            replacement = obj[key] + "-" + self._random_string()
            obj[key] = replacement
        for k, v in obj.items():
            if original and v == original:
                obj[k] = replacement
            if isinstance(v, dict):
                self._make_unique(v, key, original, replacement)
        return obj

    def _include_definition(self, include_name, schema):
        attr = include_name.split("/")
        return self._lookup(schema, *attr)

    def _include_remote_file(self, dirpath, include_name):
        _f = os.path.join(dirpath, include_name)
        if include_name not in self._included_cache:
            remote_schema = self._parse_json_include(os.path.dirname(_f), os.path.basename(_f))
            self._cleanup_before_inclusion(remote_schema)
            return remote_schema
        else:
            return self._included_cache[include_name]

    def _cleanup_before_inclusion(self, data):
        if isinstance(data, list):
            for item in data: self._cleanup_before_inclusion(item)
            return
        data.pop('$schema', None)  # remove $schema property before inclusion

    def _walk_through_to_include(self, o, dirpath):
        if isinstance(o, dict):
            is_include_exp = False
            make_unique_key = o.pop('makeUnique', None)
            if INCLUDE_KEYS[0] in o or INCLUDE_KEYS[1] in o:
                include_key = INCLUDE_KEYS[0] if INCLUDE_KEYS[0] in o else INCLUDE_KEYS[1]
                include_info, include_idx = self._get_include_name(o[include_key], INCLUDE_VALUE_PATTERNS)
                if include_info:
                    is_include_exp = True
                    include_name = include_info[0]
                    if include_idx == 0:
                        # include local definitions
                        self._included_cache[include_name] = self._include_definition(include_name,
                                                                                      self._original_schemas[-1])
                    elif include_idx in [2, 4]:
                        # include remote definitions
                        include_name = include_info[1]
                        remote_file_schema = self._include_remote_file(dirpath, include_info[0])
                        self._included_cache[include_name] = self._include_definition(include_name, remote_file_schema)
                    else:
                        # enable relative directory references: `../../`
                        self._included_cache[include_name] = self._include_remote_file(dirpath, include_name)

                    o.pop(include_key)
                    _data = self._included_cache[include_name]
                    # add data under include_key if it is not a dictionary
                    if not isinstance(_data, dict): _data = {include_key: _data}
                    o.update(self._make_unique(_data, make_unique_key) if make_unique_key else _data)
            include_text_keys = [key for key in o.keys()
                                 if isinstance(o[key], basestring) and INCLUDE_TEXT_PATTERN.search(o[key])]
            for key in include_text_keys:
                include_filename = self._get_include_name(o[key], INCLUDE_TEXT_PATTERN)
                if include_filename:
                    _f = os.path.join(dirpath, include_filename)
                    with open(os.path.join(_f)) as file:
                        o[key] = file.read()
            if is_include_exp:
                return
            for k, v in o.iteritems():
                if isinstance(v, OBJECT_TYPES):
                    self._walk_through_to_include(v, dirpath)
        elif isinstance(o, list):
            for i in o:
                if isinstance(i, OBJECT_TYPES):
                    self._walk_through_to_include(i, dirpath)

    def _parse_json_include(self, dirpath, filename):
        filepath = os.path.join(dirpath, filename)
        json_str = self._read_file(filepath)
        d = self._resolve_extend_replace(json_str, filepath)
        self._original_schemas.append(d)

        self._walk_through_to_include(d, dirpath)
        self._original_schemas.pop()

        return d

    def build_json_include(self, dirpath, filename, indent=4):
        """Parse a json file and build it by the include expression recursively.

        :param str dirpath: The directory path of source json files.
        :param str filename: The name of the source json file.
        :return: A json string with its include expression replaced by the indicated data.
        :rtype: str
        """
        self._included_cache = {}
        self._original_schemas = []
        d = self._parse_json_include(dirpath, filename)
        return json.dumps(d, indent=indent, separators=(',', ': '))

    def _build_json_include_to_files(self, dirpath, filenames, target_dirpath, indent=4):
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
            json = self.build_json_include(dirpath, i, indent)
            target_filepath = os.path.join(target_dirpath, i)
            with open(target_filepath, 'w') as f:
                f.write(json)

    def _resolve_extend_replace(self, str, filepath):
        """
        Resolve the content `$extend` and `$replace` keys:

        {
            "$extend": {
                "name": "parent.json"
            },
            "$replace": [
                {
                    "where": {
                        "key": "units",
                        "idx": 4
                    },
                    "with": "$this.units"
                },

        :param str str: json string with file content
        :param str filepath: path to the file
        :rtype: dict
        """
        obj = json.loads(str, object_pairs_hook=OrderedDict)
        if not isinstance(obj, dict):
            return obj
        extend = obj.get("$extend", {})
        replace = obj.get("$replace", {})
        filename = extend.get("name", None)
        if filename:
            json_string = self._read_file(os.path.join(os.path.dirname(filepath), filename))
            json_data = json.loads(json_string, object_pairs_hook=OrderedDict)
            for entry in replace:
                key = entry["where"]["key"]
                idx = entry["where"].get("idx", None)
                idx_cache = 0
                _with = entry["with"]
                _replacement = obj.get(_with.replace("$this.", "")) if _with and "$this." in _with else _with
                _current_value = json_data[key]
                if (idx or idx == 0) and isinstance(_current_value, list):
                    del _current_value[idx]
                    if isinstance(_replacement, list):
                        for _in, _el in enumerate(_replacement):
                            _current_value.insert(idx + _in, _el)
                            idx_cache += 1
                    else:
                        _current_value.insert(idx, _replacement)
                    _replacement = _current_value
                json_data[key] = _replacement
            obj = json_data
        return obj


def build_json(dirpath, filename, indent=4):
    return JSONInclude().build_json_include(dirpath, filename, indent)
