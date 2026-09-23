from collections import deque
from pathlib import Path

from PIL import Image

source_path = Path("frontend/public/logoloading.png")
source = Image.open(source_path).convert("RGBA")
width, height = source.size
pixels = source.load()

is_dark = [False] * (width * height)
for y in range(height):
    for x in range(width):
        red, green, blue, _ = pixels[x, y]
        is_dark[y * width + x] = red < 90 and green < 105 and blue < 135 and blue - red > 8

background = bytearray(width * height)
queue = deque()
for x in range(width):
    queue.extend(((x, 0), (x, height - 1)))
for y in range(height):
    queue.extend(((0, y), (width - 1, y)))

while queue:
    x, y = queue.popleft()
    index = y * width + x
    if background[index] or not is_dark[index]:
        continue
    background[index] = 1
    if x:
        queue.append((x - 1, y))
    if x + 1 < width:
        queue.append((x + 1, y))
    if y:
        queue.append((x, y - 1))
    if y + 1 < height:
        queue.append((x, y + 1))

variants = {
    "logoloading-white.png": ((247, 247, 245, 255), (29, 53, 87, 255)),
    "logoloading-gray.png": ((236, 236, 235, 255), None),
    "logoloading-navy.png": ((32, 42, 70, 255), None),
}

source_background = (21, 36, 58)
source_background_luminance = sum(source_background) / 3

for filename, (background_color, light_color) in variants.items():
    image = source.copy()
    output = image.load()
    for y in range(height):
        for x in range(width):
            index = y * width + x
            red, green, blue, alpha = pixels[x, y]
            if background[index]:
                output[x, y] = background_color
            elif light_color and max(red, green, blue) - min(red, green, blue) < 35 and red > 130:
                source_luminance = (red + green + blue) / 3
                coverage = max(0, min(1, (source_luminance - source_background_luminance) / (255 - source_background_luminance)))
                output[x, y] = tuple(round((1 - coverage) * background_color[channel] + coverage * light_color[channel]) for channel in range(3)) + (alpha,)
    image.save(source_path.parent / filename)
