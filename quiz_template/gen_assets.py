import os
import sys
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = 'fonts/Poppins-Bold.ttf'
ASSETS_DIR = 'assets'

def create_rounded_rect(width, height, radius, color):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=color)
    return img, draw

def create_button(text, color, text_color, filename):
    width = 460
    height = 120
    img, draw = create_rounded_rect(width, height, 60, color)
    font = ImageFont.truetype(FONT_PATH, 50)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (width - text_w) / 2
    text_y = (height - text_h) / 2 - 12 
    draw.text((text_x, text_y), text, font=font, fill=text_color)
    img.save(os.path.join(ASSETS_DIR, filename))

print("Generating buttons...")
create_button('SUBSCRIBE', (230, 40, 40, 255), (255, 255, 255, 255), 'btn_sub.png')
create_button('✓ SUBSCRIBED', (80, 80, 80, 255), (200, 200, 200, 255), 'btn_subbed.png')

print("Generating cursor...")
img = Image.new('RGBA', (140, 140), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
shadow = [(25, 25), (25, 105), (50, 80), (70, 115), (85, 105), (65, 75), (105, 75)]
out_poly = [(20, 20), (20, 100), (45, 75), (65, 110), (80, 100), (60, 70), (100, 70)]
in_poly  = [(24, 28), (24, 91),  (48, 68), (67, 103), (73, 99), (54, 63), (89, 63)]
draw.polygon(shadow, fill=(0,0,0,100))
draw.polygon(out_poly, fill=(255,255,255,255))
draw.polygon(in_poly, fill=(0,0,0,255))
img.save(os.path.join(ASSETS_DIR, 'cursor.png'))

print('Assets created!')
