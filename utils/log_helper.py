import logging

def get_logger_module(module_name):
    return logging.getLogger('fcb.' + module_name)

def get_logger_for(instance):
    return get_logger_module(instance.__class__.__name__)
