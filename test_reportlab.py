from reportlab.pdfgen import canvas
c = canvas.Canvas("test_draw.pdf")
y = 400
x = 100
c.line(x, y, x + 200, y)
c.drawImage("/Users/tylercombs/Library/CloudStorage/GoogleDrive-tylercombs@gmail.com/Shared drives/Combslink/Assets_Library/Executive-Assistant/profiles/signature/initials.png", x, y, width=100, height=50)
c.save()
