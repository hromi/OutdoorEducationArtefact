#convert an ordinary filoe (JPG, PNG u.s.w) into a bytearray which can be immediately displayed on a 5.65 colored e-ink waveshare screen
#based on https://github.com/plotto/epd565/ and https://github.com/waveshare/e-Paper/blob/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd5in65f.py

from PIL import Image, ImageEnhance
import numpy as np
from io import BytesIO
import argparse
import zipfile
import serial, time
from hashlib import md5
from math import ceil

def getbuffer(image,f):
    # Create a pallette with the 7 colors supported by the panel
    pal_image = Image.new("P", (1,1))
    pal_image.putpalette( (0,0,0,  255,255,255,  0,255,0,   0,0,255,  255,0,0,  255,255,0, 255,128,0) + (0,0,0)*249)

    # Check if we need to rotate the image
    imwidth, imheight = image.size
    if(imwidth == 600 and imheight == 448):
        image_temp = image
    elif(imwidth == 448 and imheight == 600):
        image_temp = image.rotate(90, expand=True)
    else:
        logger.warning("Invalid image dimensions: %d x %d, expected %d x %d" % (imwidth, imheight, 600, 448))

    # Convert the soruce image to the 7 colors, dithering if needed
    image_7color = image_temp.convert("RGB").quantize(palette=pal_image)
    buf_7color = bytearray(image_7color.tobytes('raw'))

    # PIL does not support 4 bit color, so pack the 4 bits of color
    # into a single byte to transfer to the panel
    buf = [0x00] * int(600 * 448 / 2)
    idx = 0
    for i in range(0, len(buf_7color), 2):
        #buf[idx] = (buf_7color[i] << 4) + buf_7color[i+1]
        f.write(((buf_7color[i] << 4) + buf_7color[i+1]).to_bytes(1,byteorder='big'))
        #idx += 1

    #return buf


parser = argparse.ArgumentParser(description='Prepare an image for Waveshare 5.65inch ACeP 7-Color E-Paper E-Ink Display Module.')
parser.add_argument('-i', help='input file',required=True)
parser.add_argument('--keepPalette', help='skip fitting to eink palette (still hotswaps in the eink palette)',action="store_true")
parser.add_argument('-o', help='output file')
parser.add_argument('--colors', help='output colors',default="RGBYOKW")
parser.add_argument('-r', type=float, help='red intensity scalar')
parser.add_argument('-g', type=float, help='green intensity scalar')
parser.add_argument('-b', type=float, help='blue intensity scalar')
parser.add_argument('--top', type=int, help='distance from top for crop')
parser.add_argument('--bottom', type=int, help='distance from top for crop')
parser.add_argument('--left', type=int, help='distance from left for crop')
parser.add_argument('--right', type=int, help='distance from left for crop')
parser.add_argument('--lightness', type=float, help='lighten/darken scalar')
parser.add_argument('--saturation', type=float, help='color saturation scalar')
parser.add_argument('--contrast', type=float, help='contrast scalar')
parser.add_argument('-p', help='serial port', nargs='?',const="/dev/cu.SLAB_USBtoUART")
parser.add_argument('-br', help='serial baudrate', type=int, default=115200)
parser.add_argument('-c', help='how many times to clear-cycle the eInk screen', type=int, default=1 )
parser.add_argument('--showEinkPalette', help='show eink paletted bmp', action="store_true")
args = vars(parser.parse_args())

assert((args['left'] != None and args['right'] == None) or (args['left'] == None and args['right'] != None) or (args['left'] == None and args['right'] == None))
assert((args['top'] != None and args['bottom'] == None) or (args['top'] == None and args['bottom'] != None) or (args['top'] == None and args['bottom'] == None))
# this is the palette with the RGB values needed to drive the eink display


activeColors = [char for char in args['colors']]
eInkDrivingPaletteBytes= { "R": [0x00, 0x00, 0xFF, 0x00], "G": [0x00, 0xFF, 0x00, 0x00], "B": [0xFF, 0x00, 0x00, 0x00], "Y": [0x00, 0xFF, 0xFF, 0x00], "O": [0x00, 0x80, 0xFF, 0x00], "K": [0x00, 0x00, 0x00, 0x00], "W": [0xFF, 0xFF, 0xFF, 0xFF] }
eInkTruePaletteBytes= { "R": [0x5D, 0x5A, 0x92, 0x00], "G": [0x54, 0x73, 0x50, 0x00], "B": [0x74, 0x5B, 0x52, 0x00], "Y": [0x60, 0xA0, 0xA0, 0x00], "O": [0x61, 0x7E, 0xA5, 0x00], "K": [0x40, 0x40, 0x40, 0x00], "W": [0xB2, 0xB1, 0xB1, 0x00] }
targetPalette= { "R": [0x92, 0x5a, 0x5d], "G": [0x50, 0x73, 0x54], "B": [0x52, 0x5b, 0x74], "Y": [0xa0, 0xa0, 0x60], "O": [0xa5, 0x7e, 0x61], "K": [0x20, 0x20, 0x20], "W": [0xb1, 0xb1, 0xb2] }

# this is the palette with the actual display colors, used for dithering accurately
paletteImage = Image.new('P', (1, 1))

paletteImage.putpalette(([int(byte) for colorBytes in [targetPalette[color] for color in activeColors] for byte in colorBytes] * ceil(768.0/(len(activeColors)*3)))[:768])

# target image size
(targetwidth, targetheight) = (600.0, 448.0)

# open the image and make sure it's in RGB mode
im = Image.open(args['i'])
im = im.convert("RGB")

#crop arguments


# rotate to horizontal
(width, height) = im.size
if width < height:
  im = im.transpose(Image.ROTATE_90)
  (width, height) = im.size
  if args['top'] != None or args['left'] != None:
    temp = args['left']
    args['left'] = args['top']
    args['top'] = temp
 

# resize and crop based on relative aspect ratio to make
#   sure there is no empty space
# todo: add top/left args for positioning the crop
# if it's too tall, fit on width and crop height
if width/height < targetwidth/targetheight:
  percent = targetwidth / float(width)
  im = im.resize((int(width * percent),int(height * percent)))
  left = 0
  if args['top'] != None:
    top = args['top']
  elif args['bottom'] != None:
    top = int(height * percent) - args['bottom'] - 448
  else:
    top = int((height * percent - targetheight) / 2)
  right = 600
  if args['top'] != None:
    bottom = args['top'] + 448
  elif args['bottom'] != None:
    bottom = int(height * percent) - args['bottom']
  else:
    bottom = int((height * percent - targetheight) / 2) + 448
  im = im.crop((left,top,right,bottom))
# if it's too wide, fit on height and crop width
else:
  percent = targetheight / float(height)
  im = im.resize((int(width * percent),int(height * percent)))
  if args['left'] != None:
    left = args['left']
  elif args['right'] != None:
    left = int(width * percent) - args['right'] - 600
  else:
    left = int((width * percent - targetwidth) / 2)
  top = 0
  if args['left'] != None:
    right = args['left'] + 600
  elif args['right'] != None:
    right = int(width * percent) - args['right']
  else:
    right = int((width * percent - targetwidth) / 2) + 600
  bottom = 448
  im = im.crop((left,top,right,bottom))

  
# allow for color intensity options
if args['r'] != None or args['g'] != None or args['b'] != None:
  (r,g,b) = [np.array(chan,dtype=np.uint16) for chan in im.split()]
  channels = { 'r': r, 'g': g, 'b': b }
  for chan in channels:
    if args[chan] != None:
      channels[chan] = channels[chan] * args[chan]
      channels[chan] = channels[chan].clip(0,255)
  im = Image.merge("RGB",[Image.fromarray(channels[chan].astype(np.uint8)) for chan in ('r','g','b')])

if args['saturation'] != None:
  saturator = ImageEnhance.Color(im)
  im = saturator.enhance(args['saturation'])

if args['lightness']:
  lightnessor = ImageEnhance.Brightness(im)
  im = lightnessor.enhance(args['lightness'])

if args['contrast']:
  contrastor = ImageEnhance.ContrastEink(im)
  im = contrastor.enhance(args['contrast'])



# convert input image to real color dithered
if not args["keepPalette"]:
  im.load()
  paletteImage.load()
  newim = im.im.convert("P",True,paletteImage.im)
  im = im._new(newim)

if not args["o"] and not args["p"] and not args["showEinkPalette"]:
  im.show()

# get the dithered images bytes and hot swap out the real color
#   palette for the eink color palette
ba = BytesIO()
im.save(ba, format='BMP')
#print(ba.getvalue())
ba = bytearray(ba.getvalue())
ba[54:1078] = bytearray(([byte for colorBytes in [eInkDrivingPaletteBytes[color] for color in activeColors] for byte in colorBytes] * ceil(1024.0/(len(activeColors)*4)))[:1024])
#ba[108:1078] = bytearray(([byte for colorBytes in [eInkDrivingPaletteBytes[color] for color in activeColors] for byte in colorBytes] * ceil(1024.0/(len(activeColors)*4)))[:1024])
#ba[0:1024] = bytearray(([byte for colorBytes in [eInkDrivingPaletteBytes[color] for color in activeColors] for byte in colorBytes] * ceil(1024.0/(len(activeColors)*4)))[:1024])
#ba[54:1078] = finalPaletteByteArray

# reload bytes as an image, and convert again to RGB to mimic the eink demo bmp
# which had a palette but also RGB values for each pixel
# todo: is this necessary?
im = Image.open(BytesIO(ba))
im = im.convert("RGB")
if not args["o"] and not args["p"] and args["showEinkPalette"]:
  im.show()

# save to file?
if args["o"]:
  #im.save(args["o"],format="BMP")
  f = open(args['o'], 'wb')
  b=getbuffer(im,f)
  f.close()


