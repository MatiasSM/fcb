import logging

def get_logger_module(module_name):
    return logging.getLogger('fcb.' + module_name)