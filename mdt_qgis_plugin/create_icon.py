import struct
import zlib
import os

def create_png(width, height, color_rgb):
    # Valid PNG Signature
    png_signature = b'\x89PNG\r\n\x1a\n'
    
    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data + 
                struct.pack('>I', zlib.crc32(tag + data)))
    
    # IHDR: width, height, bit_depth=8, color_type=2(TrueColor), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)
    
    # IDAT (Image Data)
    # Scanlines: Filter byte (0) + RGB data for each pixel
    # color_rgb must be bytes like b'\xFF\x00\x00'
    line_data = b'\x00' + (color_rgb * width)
    raw_data = line_data * height
    idat_data = zlib.compress(raw_data)
    idat = chunk(b'IDAT', idat_data)
    
    # IEND
    iend = chunk(b'IEND', b'')
    
    return png_signature + ihdr + idat + iend

# Create 32x32 blue icon
icon_params = (32, 32, b'\x00\x7F\xFF') # Azure blue
icon_data = create_png(*icon_params)

target_path = r'C:\Eduardo\Python\MDT\MDT_System_2\MDT_QGIS_Plugin\icon.png'
os.makedirs(os.path.dirname(target_path), exist_ok=True)
with open(target_path, 'wb') as f:
    f.write(icon_data)
    
print(f"Icon created at {target_path}")
