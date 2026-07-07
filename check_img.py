from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

c = canvas.Canvas("test_sig.pdf", pagesize=letter)
c.line(100, 400, 300, 400) # visual line
c.drawString(100, 400, "Sign Here:")

# draw image using same logic
fill_y = 400
img_path = "/Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles/signature/signature.png"
img_w, img_h = 252, 116
scale = 0.5
scaled_w = img_w * scale
scaled_h = img_h * scale

draw_y = fill_y - (scaled_h * 0.3)
draw_x = 180
c.drawImage(img_path, draw_x, draw_y, width=scaled_w, height=scaled_h, mask="auto")

# second image at 50%
draw_y2 = fill_y - (scaled_h * 0.5)
c.drawImage(img_path, draw_x + 100, draw_y2, width=scaled_w, height=scaled_h, mask="auto")
c.save()
