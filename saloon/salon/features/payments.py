from urllib.parse import quote, urlencode


def build_upi_payment_payload(salon, bill):
    if not salon.upi_id:
        return {}

    amount = bill.balance_due if bill.balance_due and bill.balance_due > 0 else bill.total_amount
    payee_name = salon.upi_payee_name or salon.name
    note = f"Salon bill {bill.bill_number}"
    params = {
        "pa": salon.upi_id.strip(),
        "pn": payee_name.strip(),
        "am": f"{amount:.2f}",
        "cu": "INR",
        "tn": note,
    }
    upi_url = f"upi://pay?{urlencode(params)}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data={quote(upi_url, safe='')}"
    return {
        "upi_url": upi_url,
        "qr_url": qr_url,
        "amount": amount,
        "payee_name": payee_name,
    }

