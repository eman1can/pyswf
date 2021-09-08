"""
SWF
"""
from __future__ import absolute_import
from .tag import SWFTimelineContainer
from .stream import SWFStream
from .export import SVGExporter
from six.moves import cStringIO
from io import BytesIO

class SWFHeaderException(Exception):
    """ Exception raised in case of an invalid SWFHeader """
    def __init__(self, message):
         super(SWFHeaderException, self).__init__(message)

class SWFHeader(object):
    """ SWF header """
    def __init__(self, stream):
        a = stream.readUI8()
        b = stream.readUI8()
        c = stream.readUI8()
        self._version = stream.readUI8()
        
        if self._version > 0x06:
            # FWS Uncompressed
            # CWS Compressed with zlib
            # ZFS Compressed with lzma
            if a not in [0x46, 0x43, 0x5A] or b != 0x57 or c != 0x53:
                raise SWFHeaderException("Invalid SWF Signature!")
            self._compressed_zlib = (a == 0x43)
            self._compressed_lzma = (a == 0x5A)
        else:
            # FWS Uncompressed
            # FWC Compressed with zlib
            # FWZ Compressed with lzma
            if a != 0x43 or b != 0x57 or c not in [0x53, 0x43, 0x5A]:
                raise SWFHeaderException("Invalid SWF Signature!")
            self._compressed_zlib = (c == 0x43)
            self._compressed_lzma = (c == 0x5A)
        
        self._file_length = stream.readUI32()
    
    def save(self, file, stream):
        if self._version > 0x06:
            if self._compressed_zlib:
                stream.writeUI8(file, 0x43)
            elif self._compressed_lzma:
                stream.writeUI8(file, 0x5A)
            else:
                stream.writeUI8(file, 0x46)
            stream.writeUI8(file, self._version)
            stream.writeUI32(file, self._file_length)
    
    @property
    def frame_size(self):
        return self._frame_size

    @frame_size.setter
    def frame_size(self, new_frame_size):
        self._frame_size = new_frame_size

    @property
    def frame_rate(self):
        return self._frame_rate

    @frame_rate.setter
    def frame_rate(self, new_frame_rate):
        self._frame_rate = new_frame_rate

    @property
    def frame_count(self):
        return self._frame_count

    @frame_count.setter
    def frame_count(self, new_frame_count):
        self._frame_count = new_frame_count
                
    @property
    def file_length(self):
        return self._file_length
                    
    @property
    def version(self):
        return self._version
                
    @property
    def compressed(self):
        return self._compressed_zlib or self._compressed_lzma

    @property
    def compressed_zlib(self):
        return self._compressed_zlib

    @property
    def compressed_lzma(self):
        return self._compressed_lzma
        
    def __str__(self):
        return "   [SWFHeader]\n" + \
            "       Version: %d\n" % self.version + \
            "       FileLength: %d\n" % self.file_length + \
            "       FrameSize: %s\n" % self.frame_size.__str__() + \
            "       FrameRate: %d\n" % self.frame_rate + \
            "       FrameCount: %d\n" % self.frame_count

class SWF(SWFTimelineContainer):
    """
    SWF class
    
    The SWF (pronounced 'swiff') file format delivers vector graphics, text, 
    video, and sound over the Internet and is supported by Adobe Flash
    Player software. The SWF file format is designed to be an efficient 
    delivery format, not a format for exchanging graphics between graphics 
    editors.
    
    @param file: a file object with read(), seek(), tell() methods.
    """
    def __init__(self, file=None, chunk_size=4096):
        super(SWF, self).__init__()
        self._chunk_size = 4096
        self._data = None if file is None else SWFStream(file)
        self._header = None
        if self._data is not None:
            self.parse(self._data)
    
    @property
    def data(self):
        """
        Return the SWFStream object (READ ONLY)
        """
        return self._data
    
    @property
    def header(self):
        """ Return the SWFHeader """
        return self._header
        
    def export(self, exporter=None, force_stroke=False):
        """
        Export this SWF using the specified exporter. 
        When no exporter is passed in the default exporter used 
        is swf.export.SVGExporter.
        
        Exporters should extend the swf.export.BaseExporter class.
        
        @param exporter : the exporter to use
        @param force_stroke : set to true to force strokes on fills,
                              useful for some edge cases.
        """
        exporter = SVGExporter() if exporter is None else exporter
        if self._data is None:
            raise Exception("This SWF was not loaded! (no data)")
        if len(self.tags) == 0:
            raise Exception("This SWF doesn't contain any tags!")
        return exporter.export(self, force_stroke)
            
    def parse_file(self, filename):
        """ Parses the SWF from a filename """
        with open(filename, 'rb') as file:
            self.parse(SWFStream(file))
        
    def parse(self, data):
        """ 
        Parses the SWF.
        
        The @data parameter can be a file object or a SWFStream
        """
        self._data = data if isinstance(data, SWFStream) else SWFStream(data)
        self._header = SWFHeader(self._data)
        if self._header.compressed:
            if self._header.compressed_zlib:
                self._data = SWFStream(self.decompress_zlib())
            else:
                self._data = SWFStream(self.decompress_lzma())
        self._header.frame_size = self._data.readRECT()
        self._header.frame_rate = self._data.readFIXED8()
        self._header.frame_count = self._data.readUI16()
        # self.parse_tags(self._data)
    
    def save_file(self, filename):
        with open(filename, 'wb') as file:
            self.save(file)
    
    def save(self, file):
        self._header.save(file, self._data)
        if self._header.compressed():
            output_buffer = BytesIO()
        else:
            output_buffer = file
        
        self._data.writeRECT(output_buffer, self._header.frame_size)
        self._data.writeFIXED8(output_buffer, self._header.frame_rate)
        self._data.writeUI16(output_buffer, self._header.frame_count)
        
        self.save_tags(self._data, output_buffer)
        
        if self._header.compressed():
            if self._header.compressed_zlib():
                output_buffer = self.compress_zlib(output_buffer)
            else:
                output_buffer = self.compress_lzma(output_buffer)
            
            data_chunk = output_buffer.read(self._chunk_size)
            while data_chunk:
                file.write(data_chunk)
                data_chunk.read(self._chunk_size)
    
    def decompress_zlib(self):
        from zlib import decompressobj
        decompress_method = decompressobj()
        return self.decompress(decompress_method, self._data.f)
    
    def decompress_lzma(self):
        from pylzma import decompress
        return self.decompress(decompress, self._data.f)
    
    def decompress(decompress_method, input_buffer):
        data_chunk = input_buffer.read(self._chunk_size)
        output_buffer = BytesIO()
        while data_chunk:
            data = decompress_method(data_chunk)
            output_buffer.write(data)
            data_chunk = input_buffer.read(self._chunk_size)
        output_buffer.seek(0)
        return output_buffer
    
    def compress(compress_method, input_buffer):
        data_chunk = input_buffer.read(self._chunk_size)
        output_buffer = BytesIO()
        while data_chunk:
            data = compress_method(data_chunk)
            output_buffer.write(data)
            data_chunk = input_buffer.read(self._chunk_size)
        output_buffer.seek(0)
        return output_buffer
    
    def compress_zlib(self, input_buffer):
        from zlib import compressobj
        compress_method = compressobj()
        return self.compress(compress_method, input_buffer)
    
    def compress_lzma(self, input_buffer):
        from pylzma import compress
        return self.compress(compress, input_buffer)
    
    def __str__(self):
        s = "[SWF]\n"
        s += self._header.__str__()
        for tag in self.tags:
            s += tag.__str__() + "\n"
        return s
        
