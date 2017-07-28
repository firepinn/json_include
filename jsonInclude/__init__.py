from main import JSONInclude


def build_json(dirpath, filename, indent=4):
    return JSONInclude().build_json_include(dirpath, filename, indent)
