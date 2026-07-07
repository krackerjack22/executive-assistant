from reportlab.pdfgen import canvas
c = canvas.Canvas("test_rl.pdf", pagesize=(200, 200))
# Draw a line at y=100
c.line(0, 100, 200, 100)
# Draw an image at y=100 - (h*0.04)
# Let's just draw a rect instead of an image to simulate
h = 50
c.rect(50, 100 - (h*0.04), 50, h)
c.save()
