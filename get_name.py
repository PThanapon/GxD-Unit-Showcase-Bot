import easyocr
from PIL import Image

def get_name():
    image_path = 'submitted_image.png'
    img = Image.open(image_path)
    width, height = img.size
    new_width = width // 2
    new_height = height // 10
    left = 0
    top = 0
    right = new_width
    bottom = new_height
    cropped_img = img.crop((left, top, right, bottom))
    cropped_img.save("cropped.png")

    reader = easyocr.Reader(['en'])  # Specify languages to be used (e.g., English)

    # Read the image file and perform OCR
    results = reader.readtext("cropped.png")
    # Extract and print the text
    return results[0][1]

if __name__ == "__main__":
    get_name()