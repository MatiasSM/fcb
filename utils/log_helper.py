import logging

def get_logger_module(module_name):
    return logging.getLogger('fcb.' + module_name)

def get_logger_for(instance):
    return get_logger_module(instance.__class__.__name__)

def _do_deep_print(instance, level):
    levels_lines = []
    for attr in instance.__dict__.keys():
        if attr == "log" or attr == "_log":
            continue
        val = getattr(instance, attr)
        if isinstance(val, (bool, int, float, str, unicode, list, dict, set)) or val is None:
            levels_lines.append("{pad}{field}: {value}".format(pad=level * '  ', field=attr, value=val))
        else:
            levels_lines.append("{pad}{field}:".format(pad=level * '  ', field=attr))
            levels_lines.extend(_do_deep_print(val, level=level+1))
    return levels_lines

# TODO MOVE
def deep_print(instance, header=None):
    levels_lines = [] if header is None else [header]
    levels_lines.extend(_do_deep_print(instance, level=len(levels_lines)))
    return "\n".join(levels_lines)
