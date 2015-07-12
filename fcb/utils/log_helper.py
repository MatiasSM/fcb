import logging


def get_logger_module(module_name):
    return logging.getLogger('fcb.' + module_name)


def get_logger_for(instance):
    return get_logger_module(instance.__class__.__name__)


_pad_value_fmt_str = "{pad}{value}"
_pad_field_fmt_str = "{pad}{field}:"
_pad_field_value_fmt_str = _pad_field_fmt_str + " {value}"


def _level_pad(level):
    return level * '  '


def _print_dict(inst_dic, level):
    levels_lines = []
    level_pad = _level_pad(level)
    fields_level = level + 1
    fields_level_pad = _level_pad(fields_level)
    for key, value in inst_dic.items():
        levels_lines.append(_pad_field_fmt_str.format(pad=level_pad, field="*"))
        levels_lines.append(_pad_field_fmt_str.format(pad=fields_level_pad, field="key"))
        levels_lines.extend(_do_deep_print(key, fields_level + 1))
        levels_lines.append(_pad_field_fmt_str.format(pad=fields_level_pad, field="value"))
        levels_lines.extend(_do_deep_print(value, fields_level + 1))
    return levels_lines


def _print_list(inst_list, level):
    levels_lines = []
    item_idx = 0
    level_pad = _level_pad(level)
    for instance in inst_list:
        levels_lines.append(_pad_field_fmt_str.format(pad=level_pad, field=item_idx))
        levels_lines.extend(_do_deep_print(instance, level + 1))
        item_idx += 1
    return levels_lines


def _is_plain_type(instance):
    return isinstance(instance, (bool, int, float, str, unicode)) or instance is None


def _should_ignore_key(key):
    return key in ("log", "_log", "upath", "_unit_factor")


def _should_ignore_value(instance):
    return not hasattr(instance, '__dict__') or hasattr(instance, '__call__')


def _do_deep_print(instance, level):
    levels_lines = []
    level_pad = _level_pad(level)

    if _is_plain_type(instance):
        levels_lines.append(_pad_value_fmt_str.format(pad=level_pad, value=instance))
    elif not _should_ignore_value(instance):
        keys = instance.__dict__.keys()
        keys.extend([k for k in instance.__class__.__dict__.keys() if not k.endswith("__")])
        for attr in set(keys):
            if _should_ignore_key(attr):
                continue
            val = getattr(instance, attr)
            if isinstance(val, dict):
                levels_lines.append(_pad_field_value_fmt_str.format(pad=level_pad, field=attr, value="{"))
                levels_lines.extend(_print_dict(val, level=level + 1))
                levels_lines.append(_pad_value_fmt_str.format(pad=level_pad, value="}"))
            elif isinstance(val, (list, set)):
                levels_lines.append(_pad_field_value_fmt_str.format(pad=level_pad, field=attr, value="["))
                levels_lines.extend(_print_list(val, level=level + 1))
                levels_lines.append(_pad_value_fmt_str.format(pad=level_pad, value="]"))
            elif _is_plain_type(val):
                levels_lines.append(_pad_field_value_fmt_str.format(pad=level_pad, field=attr, value=val))
            elif not _should_ignore_value(val):
                levels_lines.append(_pad_field_fmt_str.format(pad=level_pad, field=attr))
                levels_lines.extend(_do_deep_print(val, level=level + 1))
    return levels_lines


# TODO MOVE
def deep_print(instance, header=None):
    levels_lines = [] if header is None else [header]
    levels_lines.extend(_do_deep_print(instance, level=len(levels_lines)))
    return "\n".join(levels_lines)
