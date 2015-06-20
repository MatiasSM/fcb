from copy import deepcopy
import tarfile
import tempfile
from datetime import datetime
import os

from framework.workflow.PipelineTask import PipelineTask
from processing.filesystem.FileInfo import FileInfo
from utils.log_helper import get_logger_for, get_logger_module, deep_print


class Block(object):
    def __init__(self, destinations):
        self.log = get_logger_for(self)
        self.destinations = destinations

        self._content_size = 0
        self._content_file_infos = []
        self._fragmented_files = []
        self._processed_data_file_info = None
        self._latest_file_info = None
        self.all_gen_files = []

    @property
    def latest_file_info(self):
        return self._latest_file_info

    @latest_file_info.setter
    def latest_file_info(self, value):
        if self._latest_file_info != value:
            self._latest_file_info = value
            self.all_gen_files.append(value)

    @property
    def fragmented_files(self):
        return self._fragmented_files

    @property
    def processed_data_file_info(self):
        return self._processed_data_file_info

    @property
    def content_file_infos(self):
        return self._content_file_infos

    @property
    def content_size(self):
        return self._content_size

    def add(self, file_info):
        self.log.debug(deep_print(file_info, "Added to block ({:02X}):".format(id(self))))
        self._content_size += file_info.size
        self._content_file_infos.append(file_info)
        self.log.debug("Block content size: {}".format(self._content_size))

    def finish(self):
        of = tempfile.NamedTemporaryFile(
            suffix=".tar.bz2",
            prefix="_".join(("archive", datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f'), "")),
            delete=False)
        output_filename = of.name
        of.close()
        with tarfile.open(output_filename, "w:bz2") as tar:
            for file_info in self._content_file_infos:
                tar.add(file_info.path, arcname=file_info.basename)
            tar.close()
        self._processed_data_file_info = FileInfo(output_filename)
        self.latest_file_info = self._processed_data_file_info
        self.log.debug("Created %s", output_filename)


class FragmentInfo(object):
    def __init__(self, file_info, fragment_num, fragments_count):
        self.file_info = file_info
        self.fragment_num = fragment_num
        self.fragments_count = fragments_count


class _BlockFragmenter(object):
    """
    Handles the logic to check if/how new content can be fit into a block
    """
    def __init__(self, sender_spec, should_split_small_files):
        self.log = get_logger_for(self)
        self._max_upload_per_day_in_bytes = sender_spec.restrictions.max_upload_per_day_in_bytes
        self._max_size_in_bytes = sender_spec.restrictions.max_size_in_bytes
        self._bytes_uploaded_today = sender_spec.bytes_uploaded_today
        self._max_files_per_container = sender_spec.restrictions.max_files_per_container
        self._should_split_small_files = should_split_small_files

    def does_fit_in_todays_share(self, file_info):
        return (self._max_upload_per_day_in_bytes == 0
                or file_info.size <= self._max_upload_per_day_in_bytes - self._bytes_uploaded_today)

    def can_add_new_content(self, block, file_info):
        """
        new content from file_info can be added into block iff
        - file count limit hasn't been reached for the block
        - there is enough space to completely fit the info into the block
        - OR the info can be split and some info can fit into the block
        """
        return ((self._max_files_per_container == 0 or self._max_files_per_container > len(block.content_file_infos))
                and (self.does_content_fit(file_info, block)
                     or
                     # check if we can fit some content by splitting the file
                     # Note: if max size was unlimited, does_content_fit would have been True
                     (block.content_size < self._max_size_in_bytes
                      and (self._should_split_small_files or not self._is_small_file(file_info)))))

    def get_fragments_spec(self, block):
        class Spec(object):
            def __init__(self, block_cur_size, max_size):
                self.first = max_size - block_cur_size
                self.remaining = max_size
        return Spec(block.content_size, self._max_size_in_bytes)

    def account_block(self, block):
        self._bytes_uploaded_today += block.processed_data_file_info.size
        self.log.debug("Total (pending to be) uploaded today %d bytes", self._bytes_uploaded_today)

    def has_space_left(self, block):
        return self._max_size_in_bytes == 0 or self._max_size_in_bytes > block.content_size

    def does_content_fit(self, file_info, block):
        return (self._max_size_in_bytes == 0
                or file_info.size + block.content_size <= self._max_size_in_bytes)

    @property
    def bytes_uploaded_today(self):
        return self._bytes_uploaded_today

    @property
    def max_upload_per_day_in_bytes(self):
        return self._max_upload_per_day_in_bytes

    def _is_small_file(self, file_info):
        """
        A file is considered as "small" if its content can fit into a (empty) block
        """
        return self._max_size_in_bytes != 0 and self._max_size_in_bytes >= file_info.size


class _CompressorJob(object):
    def __init__(self,
                 sender_spec,
                 tmp_file_parts_basepath,
                 should_split_small_files,
                 new_output_cb):
        self._tmp_file_parts_basepath = tmp_file_parts_basepath
        self._new_output_cb = new_output_cb
        self._destinations = sender_spec.destinations
        self._current_block = None
        self._block_fragmenter = _BlockFragmenter(sender_spec=sender_spec,
                                                  should_split_small_files=should_split_small_files)
        self.name = "".join((self.__class__.__name__, '(to ', str(self._destinations), ')'))
        self.log = get_logger_module(self.name)

    def add_destinations(self, destinations):
        self._destinations.extend(destinations)

    def process_data(self, file_info):
        # note we check against the file (despite it will be compressed, and possibly require less space) so we
        # can avoid processing it if it wouldn't fit
        if not self._block_fragmenter.does_fit_in_todays_share(file_info):
            self.log.debug("Won't try to fit file '%s' into block because adding it's size (%d)" +
                           " to the current sent amount (%d) would exceed the maximum for the day (%d)",
                           file_info.path, file_info.size, self._block_fragmenter.bytes_uploaded_today,
                           self._block_fragmenter.max_upload_per_day_in_bytes)
            return  # ignore file

        file_parts = [file_info]
        self._add_block_if_none()

        if not self._block_fragmenter.can_add_new_content(self._current_block, file_info):
            self.log.debug("Need to finish current block because file '%s' can't be added to it", file_info.path)
            self._finish_current_block(True)
        elif not self._block_fragmenter.does_content_fit(file_info, self._current_block):
            self.log.debug("File '%s' doesn't fit in the block, will need to fragment it", file_info.path)
            # split the file so the first part fits in the current block and the remaining in new blocks
            fragments_spec = self._block_fragmenter.get_fragments_spec(self._current_block)
            file_parts = self._create_fragments(file_info, fragments_spec.first,
                                                fragments_spec.remaining, self._tmp_file_parts_basepath)
            self.log.debug("File '%s' fragmented in %d parts to fit in blocks" % (file_info.path, len(file_parts)))

        fragments_count = len(file_parts)
        fragment_num = 0

        for part_file_info in file_parts:
            self._add_block_if_none()
            if fragments_count > 1:  # is fragmented
                fragment_num += 1
                part_file_info.fragment_info = FragmentInfo(file_info, fragment_num, fragments_count)
                self._current_block.fragmented_files.append(part_file_info.fragment_info)
            self._current_block.add(part_file_info)
            if not self._block_fragmenter.has_space_left(self._current_block):
                self.log.debug("No more space left in current block, will finish it")
                self._finish_current_block()

    def flush(self):
        """
            Finish processing any partly created block of information
            Should be executed when no more files are intended to be read
        """
        if self._current_block:
            self._finish_current_block()

    @staticmethod
    def _create_fragments(file_info, first_chunk_size, other_chunks_size, parts_basedir):
        result = []
        with open(file_info.path, "rb") as f:
            chunk_number = 1
            chunk = f.read(first_chunk_size)
            path_basename = file_info.basename
            while chunk:
                out_filename = "".join((os.path.join(parts_basedir, path_basename), "_part_%03d" % chunk_number))
                with open(out_filename, "wb") as outf:
                    outf.write(chunk)
                    outf.close()
                    result.append(FileInfo(out_filename))
                chunk_number += 1
                chunk = f.read(other_chunks_size)
            f.close()
        return result

    def _finish_current_block(self, should_add_new_block=False):
        self._current_block.finish()
        self._block_fragmenter.account_block(self._current_block)
        self._new_output_cb(self._current_block)
        self._current_block = None
        if should_add_new_block:
            Block(self._destinations)

    def _add_block_if_none(self):
        if not self._current_block:
            self._current_block = Block(self._destinations)


# ------------------------------------------------------


class Compressor(PipelineTask):
    restriction_to_job = {}  # keeps a map sender_spec.restrictions -> _CompressorJob

    def __init__(self, fs_settings):
        PipelineTask.__init__(self)

        fs_settings = deepcopy(fs_settings)  # because we store some of the info, we need a deep copy
        '''
        If the same restrictions are applied for many destinations, we use the same job to avoid processing
        files twice
        '''
        for sender_spec in fs_settings.sender_specs:
            restrictions = sender_spec.restrictions
            if restrictions in self.restriction_to_job:
                self.restriction_to_job[restrictions].add_destinations(sender_spec.destinations)
            else:
                self.restriction_to_job[restrictions] = _CompressorJob(sender_spec,
                                                                       fs_settings.tmp_file_parts_basepath,
                                                                       fs_settings.should_split_small_files,
                                                                       lambda data: self.new_output(data))

    # override from PipelineTask
    def process_data(self, file_info):
        for job in self.restriction_to_job.values():
            self.log.debug("Processing file by: {}".format(job.name))
            job.process_data(file_info)

    # override from PipelineTask
    def on_stopped(self):
        for job in self.restriction_to_job.values():
            job.flush()
