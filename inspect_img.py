from PIL import Image

img_path = "/Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles/signature/signature.png"
img = Image.open(img_path)
print(f"Original size: {img.size}")
bbox = img.getbbox()
print(f"Ink bounding box: {bbox}")

# initial
img2 = Image.open("/Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles/signature/initials.png")
print(f"Initial size: {img2.size}")
print(f"Initial bbox: {img2.getbbox()}")
