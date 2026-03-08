from django.shortcuts import render

# Create your views here.
import easyocr
import cv2
import numpy as np
from django.shortcuts import render
from .forms import ImageUploadForm
from django.core.files.storage import default_storage
import requests

import cv2

#def preprocess_image(image_path):
#    img = cv2.imread(image_path)
#    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#    filtered = cv2.bilateralFilter(gray, 11, 17, 17)  # Noise reduction
#    edged = cv2.Canny(filtered, 30, 200)  # Edge detection
#    _, thresh = cv2.threshold(filtered, 150, 255, cv2.THRESH_BINARY)
#    processed_path = image_path.replace(".jpg", "_processed.jpg")
#    cv2.imwrite(processed_path, thresh)
#    return processed_path

import cv2

def preprocess_image(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.bilateralFilter(gray, 11, 17, 17)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    processed_path = image_path.replace('.jpg', '_processed.jpg')
    cv2.imwrite(processed_path, thresh)
    return processed_path



def correct_ocr_errors(text):
    corrections = {
        'I': '1',
        'Z': '2',
        'O': '0',
        'Q': '0',
        'B': '8',
        'S': '5',
        'G': '6',
        # Add more based on real OCR outputs
    }

    def correct_ocr_errors(text):
        corrections = {
        'I': '1',
        'l': '1',
        'O': '0',
        'o': '0',
        'Z': '2',
        'S': '5',
        'B': '8',
        'A': '4',
        # You can add more
    }

    corrected = ''.join([corrections.get(char, char) for char in text.upper()])
    return corrected




def extract_number_plate_text(image_path):
    reader = easyocr.Reader(['en'])
    results = reader.readtext(image_path)
    print("OCR Results:", results)

    texts = [text for (_, text, prob) in results if prob > 0.3]
    combined_text = " ".join(texts).replace(" ", "").upper()
    corrected_text = correct_ocr_errors(combined_text)

    print("Corrected Text:", corrected_text)

    if is_valid_plate(corrected_text):
        return corrected_text
    return None


#def get_vehicle_info(number_plate):
    # Replace this with your actual API or database call
    # Dummy response
 #   return {
  #      "number_plate": number_plate,
   #     "owner_name": "John Doe",
    #    "vehicle_type": "SUV",
     #   "registration_date": "2022-05-10"
    #}

from fuzzywuzzy import process
from .models import Vehicle

def get_vehicle_info(ocr_plate):
    all_plates = Vehicle.objects.values_list('plate_number', flat=True)
    best_match, score = process.extractOne(ocr_plate.upper(), all_plates)

    if score > 80:  # Confidence threshold
        vehicle = Vehicle.objects.get(plate_number=best_match)
        return {
            'owner_name': vehicle.owner_name,
            'vehicle_type': vehicle.vehicle_type,
            'registration_date': vehicle.registration_date,
        }
    return None




import re

def is_valid_plate(plate):
    # Example: KA01AB1234 or MH12DE1433
    return re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{3,4}$', plate) is not None



def upload_image(request):
    vehicle_info = None
    plate_text = None

    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.cleaned_data['image']
            image_path = default_storage.save('tmp/' + image.name, image)
            full_path = default_storage.path(image_path)

            # ✅ Preprocess the image safely here
            processed_path = preprocess_image(full_path)

            # ✅ Use processed image for OCR
            plate_text = extract_number_plate_text(processed_path)
            

            if plate_text:
                vehicle_info = get_vehicle_info(plate_text)
    else:
        form = ImageUploadForm()

    return render(request, 'reader/upload.html', {
        'form': form,
        'vehicle_info': vehicle_info,
        'plate_text': plate_text
    })
