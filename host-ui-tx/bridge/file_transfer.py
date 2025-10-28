"""
File transfer module for handling file data chunking and validation.
"""
import struct
import logging
import base64

LOG = logging.getLogger(__name__)

CHUNK_SIZE = 16 * 1024  # 16KB chunks to match STM32 side

def create_chunk_validator():
    """Create a simple chunk validator function"""
    def validate_chunk(chunk_data):
        return True  # Basic validation - can be enhanced with checksums
    return validate_chunk

class FileTransfer:
    def __init__(self):
        self.data = None
        self.filename = None
        self.size = 0
        self.current_chunk = 0
        self.total_chunks = 0
        self.validator = create_chunk_validator()
    
    def prepare_file(self, file_data: str, filename: str):
        """Prepare a file for transfer by decoding base64 data"""
        # Remove data URL prefix if present (e.g., "data:application/octet-stream;base64,")
        if ';base64,' in file_data:
            file_data = file_data.split(';base64,')[1]
            
        # Decode base64 data
        self.data = base64.b64decode(file_data)
        self.filename = filename
        self.size = len(self.data)
        self.current_chunk = 0
        self.total_chunks = (self.size + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        LOG.info(f"Prepared file {filename} ({self.size} bytes, {self.total_chunks} chunks)")
    
    def get_header(self) -> bytes:
        """Generate file transfer header"""
        # Header format:
        # - Magic bytes (2 bytes): 0xAA 0x55
        # - File size (4 bytes)
        # - Filename length (1 byte)
        # - Filename (variable)
        if not self.data:
            raise RuntimeError("No file prepared for transfer")
            
        magic = b'\xAA\x55'
        header = struct.pack('>2sIB', magic, self.size, len(self.filename))
        header += self.filename.encode('utf-8')
        return header
    
    def get_next_chunk(self) -> tuple[bytes, int]:
        """Get the next chunk of data to send"""
        if not self.data or self.current_chunk >= self.total_chunks:
            return None
            
        start = self.current_chunk * CHUNK_SIZE
        end = min(start + CHUNK_SIZE, self.size)
        chunk_data = self.data[start:end]
        
        # Add chunk header:
        # - Chunk number (2 bytes)
        # - Chunk size (2 bytes)
        chunk_header = struct.pack('>HH', self.current_chunk, len(chunk_data))
        
        # Combine header and data
        chunk = chunk_header + chunk_data
        
        # Validate chunk before sending
        if not self.validator(chunk):
            raise RuntimeError(f"Chunk {self.current_chunk} failed validation")
            
        chunk_num = self.current_chunk
        self.current_chunk += 1
        
        return chunk, chunk_num