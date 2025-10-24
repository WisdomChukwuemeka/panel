# payments/utils.py (new file - add this for potential use, though not directly used in payments views; useful if integrating with publications)
import requests
from django.conf import settings

def verify_paystack_payment(reference, expected_amount):
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        resp_data = response.json()
        if resp_data['status'] and resp_data['data']['status'] == 'success' and resp_data['data']['amount'] == expected_amount * 100:
            return True, resp_data['data']
    return False, None