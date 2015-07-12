from PIL import Image
import numpy
import math

from fcb.framework.workflow.PipelineTask import PipelineTask
from fcb.processing.models.FileInfo import FileInfo
from fcb.utils.log_helper import get_logger_module

_log = get_logger_module("ToImage")

# TODO image and array manipulation functions need to be optimized (a lot)

def _determine_dimensions(num_of_pixels):
    """
    Given a number of pixels, determines the largest width and height that define a
      rectangle with such an area
    """
    for x in xrange(int(math.sqrt(num_of_pixels)) + 1, 1, -1):
        if num_of_pixels % x == 0:
            return num_of_pixels // x, x
    return 1, num_of_pixels  # if no better dimensions could be found, use a "line"


def _to_image_array(file_path):
    """
    Converts the file in file_path to a numpy array (matrix) representing an RGB image
    The dimensions of the image are calculated using __determine_dimensions.
    Padding is added provide enough bytes to generate the image (between 1 and 3 bytes can be added).
    """
    _log.debug("File '%s' to image", file_path)
    data = numpy.fromfile(file_path, numpy.uint8)
    orig_len = len(data)
    pad_req = (3 - (orig_len % 3))
    pad_req += 3 if pad_req == 0 else 0
    final_len = orig_len + pad_req
    num_of_pixels = final_len // 3
    w, h = _determine_dimensions(num_of_pixels)
    reshaped = numpy.zeros((w, h, 3), dtype=numpy.uint8)
    for i in xrange(final_len):
        sidx = i // 3
        y = sidx % h
        x = sidx // h
        s = i % 3
        reshaped[x, y, s] = data[i] if i < orig_len else 0
    reshaped[-1, -1, 2] = pad_req

    return reshaped


def from_file_to_image(file_path, img_path):
    data = _to_image_array(file_path)
    img = Image.fromarray(data, 'RGB')
    img.save(img_path)


def from_image_to_file(img_path, file_path):
    """
    Expects images created by from_from_file_to_image
    """
    img = Image.open(img_path)
    data = numpy.array(img)
    data = numpy.reshape(data, len(img.getdata()) * 3)
    to_remove = data[len(data) - 1]
    data = numpy.delete(data, xrange(len(data) - to_remove, len(data)))
    data.tofile(file_path)


class ToImage(PipelineTask):
    @classmethod
    def get_extension(cls):
        return ".png"

    @classmethod
    def is_transformed(cls, path):
        return path.endswith(cls.get_extension())

    # override from PipelineTask
    def process_data(self, block):
        """
        Note: Expects Compressor Block like objects
        """
        src_file_path = block.latest_file_info.path
        img_path = src_file_path + self.get_extension()
        self.log.debug("Converting file '%s' to image '%s'", src_file_path, img_path)
        from_file_to_image(src_file_path, img_path)
        block.image_converted_file_info = FileInfo(img_path)
        block.latest_file_info = block.image_converted_file_info
        return block
