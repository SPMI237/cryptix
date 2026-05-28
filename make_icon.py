from PIL import Image, ImageDraw

# Create 256x256 image
img = Image.new("RGBA", (256, 256), "#0B0F19")

draw = ImageDraw.Draw(img)

# Draw simple circle logo
draw.ellipse((48, 48, 208, 208), fill="#00F0FF")

# Save as proper ICO
img.save(
    "cryptix.ico",
    format="ICO",
    sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
)

print("✅ cryptix.ico created successfully.")