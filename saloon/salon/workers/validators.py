import re

from django.core.exceptions import ValidationError


def validate_mobile_10(phone):
    if not phone:
        return
    if not re.fullmatch(r"\d{10}", phone):
        raise ValidationError("Mobile number must be exactly 10 digits and numeric only.")


def validate_pan_number(pan_number):
    if not pan_number:
        return
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan_number):
        raise ValidationError("PAN must be in format: ABCDE1234F")


def validate_aadhaar_number(aadhaar_number):
    if not aadhaar_number:
        return
    if not re.fullmatch(r"\d{12}", aadhaar_number):
        raise ValidationError("Aadhaar number must be exactly 12 digits.")


def validate_pincode(pincode):
    if not pincode:
        return
    if not re.fullmatch(r"\d{6}", pincode):
        raise ValidationError("Pincode must be exactly 6 digits.")

