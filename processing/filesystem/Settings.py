import tempfile

class Settings(object):
    max_size_in_bytes = 0
    max_upload_per_day_in_bytes = 0
    #output_file_basepath = None    
    tmp_file_parts_basepath = tempfile.gettempdir()
    should_split_small_files = False