"""用纯 Python 标准库生成最小可用的 .ico 图标文件（32x32 蓝色方形占位图标）"""
import struct
import os

def create_ico(path, size=32, color=(64, 128, 192)):
    """生成一个纯色方形 .ico 文件"""
    width, height = size, size
    bpp = 32
    # BGRA 像素数据（BMP 是 bottom-up）
    row_bytes = width * 4
    pixel_data = b''
    for y in range(height):
        for x in range(width):
            # 简单的圆形+PDF字样风格的色块
            r, g, b = color
            # 边框效果
            if x < 2 or x >= width - 2 or y < 2 or y >= height - 2:
                r, g, b = 30, 30, 30
            pixel_data += struct.pack('BBBB', b, g, r, 255)  # BGRA

    # BITMAPINFOHEADER (40 bytes)
    bi_size = 40
    bi_planes = 1
    bi_bit_count = bpp
    bi_compression = 0
    bi_size_image = len(pixel_data)
    bi_x_pels = 0
    bi_y_pels = 0
    bi_clr_used = 0
    bi_clr_important = 0

    bitmap_info = struct.pack('<IiiHHIIiiII',
        bi_size, width, height * 2, bi_planes, bi_bit_count,
        bi_compression, bi_size_image, bi_x_pels, bi_y_pels,
        bi_clr_used, bi_clr_important)

    # 完整的 BMP 图像数据
    bmp_data = bitmap_info + pixel_data

    # AND mask (1 bit per pixel, row-aligned to 4 bytes)
    mask_row_size = ((width + 31) // 32) * 4
    and_mask = b'\x00' * (mask_row_size * height)

    image_data = bmp_data + and_mask

    # ICO header
    ico_header = struct.pack('<HHH', 0, 1, 1)  # reserved, type=ICO, count=1

    # ICO directory entry
    image_offset = 6 + 16  # header + 1 directory entry
    dir_entry = struct.pack('<BBBBHHII',
        width if width < 256 else 0,
        height if height < 256 else 0,
        0,  # no color palette
        0,  # reserved
        1,  # color planes
        bpp,
        len(image_data),
        image_offset)

    with open(path, 'wb') as f:
        f.write(ico_header)
        f.write(dir_entry)
        f.write(image_data)

    print(f"图标已生成: {path} ({size}x{size}, {os.path.getsize(path)} bytes)")


if __name__ == '__main__':
    icon_path = os.path.join(os.path.dirname(__file__), 'app', 'resources', 'icons', 'app.ico')
    os.makedirs(os.path.dirname(icon_path), exist_ok=True)
    create_ico(icon_path)
