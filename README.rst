An extension for JSON to support file inclusion
===============================================

json-include is an extended way for JSON to support file inclusion, it has two parts:

1. A syntax definition called **include syntax**.

2. A Python implementation to parse and build JSON file that contains **include syntax**.


Syntax
------

json-include supports an extended syntax called **include syntax** in JSON,
formatted as:

.. code-block:: json

    {
        "...": "include(<json file name>)"
    }

or

.. code-block:: json

    {
        "<any key>": "include_text(<text file name>)"
    }



The include syntax means that this object (the whole ``{"...": "include(<json file name>")}``) in JSON is a reference to the JSON file named in ``<json file name>`` notation, and should be included into its place.

The included JSON should always be an object (dict) rather than an array (list), to prevent implicit meaning and make sure we can get a clear view of the structure without looking into the included JSON files.

In case multiple include statements are used, passing key inside `makeUnique` adds a random string to each included value at the corresponding key:

.. code-block:: json

    {
        "...": "include(<json file name>)",
        "makeUnique": "<key>"
    }


In a normal JSON when we want to include another JSON on an attribute, it should be written as follows:

.. code-block:: json

    {
        "username": "alice",
        "profile": {
            "...": "include(profile_model.json)"
        }
    }

In this JSON a ``profile_model.json`` is included to present ``profile`` attribute,
if the content of ``profile_model.json`` is like:

.. code-block:: json

    {
        "age": 18,
        "gender": "female"
    }

then what we mean by the include syntax is that, when this JSON is being used
as a normal JSON, it should be seen as:

.. code-block:: json

    {
        "username": "alice",
        "profile": {
            "age": 18,
            "gender": "female"
        }
    }

To ture JSON with include syntax into a normal JSON, a build process is needed,
that's what the implementation does.

Python Implementation
---------------------

Implementation could be of any language as long as it can understand the include syntax
and output as expected, this repo contains a Python implementation for use.

Installation
~~~~~~~~~~~~

::

    pip install https://github.com/exabyte-io/json_include/archive/master.zip

Usage
~~~~~

.. code-block:: python

    import json_include
    json_include.build_json(ROOT_DIR, 'example.json')

