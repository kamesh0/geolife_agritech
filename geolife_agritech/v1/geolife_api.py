import datetime
import json
import random
import frappe
from frappe import auth
import base64
import os
from frappe.utils import get_files_path, get_site_name, now, add_to_date, get_datetime, add_to_date, validate_email_address
from frappe.utils.data import escape_html
import requests
from frappe.core.doctype.user.user import test_password_strength

@frappe.whitelist(allow_guest=True)
def generate_otp(mobile_no):
    if not mobile_no :
        frappe.local.response["message"] = {
            "status": False,
            "message": "Invalid Mobile Number"
        }
        return
    
    user_email = frappe.db.get_all('User', filters={'mobile_no': mobile_no}, fields=['email'])
    if not user_email:
        frappe.local.response["message"] = {
            "status": True,
            "message": "User does not exits"
        }
        return 

    try:
        otp = "1234"
        # otp = str(random.randint(1000,9999))
        # msisdn = mobile_no #frappe.generate_hash("", 10)
        # text = f"You OTP {otp}"

        # callback_url = frappe.db.get_single_value("Geo Settings", "sms_call_back_url")
        # url = frappe.db.get_single_value("Geo Settings", "sms_base_url")
        # app_id = frappe.db.get_single_value("Geo Settings", "sms_app_id")
        # app_key = frappe.db.get_single_value("Geo Settings", "sms_app_key")

        # sms_payload = {
        #     "msisdn": msisdn,
        #     "text": text,
        #     "callback_url": callback_url,
        #     "premium": True
        # }
        # sms_headers = {
        #     "accept": "application/json",
        #     "App-ID": app_id,
        #     "API-Key": app_key,
        #     "content-type": "application/json"
        # }
        # r = requests.post(url, json=sms_payload, headers=sms_headers)

        # if r.status_code != 201:
        #     frappe.local.response["message"] = {
        #         "status": False,
        #         "message": json.loads(r.text)["message"]
        #     }
        #     return
        doc = frappe.get_doc({
            "doctype": "OTP Auth",
            "mobile_number": mobile_no,
            "otp": otp,
        })

        doc.insert(ignore_permissions=True)
        doc.save
        frappe.db.commit()
        
        frappe.local.response["message"] = {
        "status": True,
        "message": 'OTP SENT'
        }

        return

    except Exception as e:
        return e

@frappe.whitelist(allow_guest=True)
def reset_otp(mobile_no):
    generate_otp(mobile_no)

@frappe.whitelist()
def get_user_info(api_key, api_sec):
    # api_key  = frappe.request.headers.get("Authorization")[6:21]
    # api_sec  = frappe.request.headers.get("Authorization")[22:]
    doc = frappe.db.get_value(
        doctype='User',
        filters={"api_key": api_key},
        fieldname=["name"]
    )

    doc_secret = frappe.utils.password.get_decrypted_password('User', doc, fieldname='api_secret')

    if api_sec == doc_secret:
        user = frappe.db.get_value(
            doctype="User",
            filters={"api_key": api_key},
            fieldname=["name"]
        )
        return user
    else:
        return "API Mismatch"

@frappe.whitelist(allow_guest=True)
def generate_keys(user):
    user_details = frappe.get_doc("User", user)
    api_secret = frappe.generate_hash(length=15)
    
    if not user_details.api_key:
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key
    
    user_details.api_secret = api_secret

    user_details.flags.ignore_permissions = True
    user_details.save(ignore_permissions = True)
    frappe.db.commit()
    
    return user_details.api_key, api_secret

@frappe.whitelist(allow_guest=True)
def validate_otp(mobile_no, otp):

    if not mobile_no or not otp:
        frappe.local.response["message"] = {
            "status": False,
            "message": "invalid inputs"
        }
        return
    
    x_user = frappe.get_all('OTP Auth', filters={'mobile_number': mobile_no, 'otp': otp}, fields=["*"], order_by= 'creation desc')

    # if x_user[0].otp != otp:
    #     frappe.local.response["message"] = {
    #         "status": False,
    #         "message": "Invalid OTP"
    #     }
    #     return

    if x_user:
        now_time = now()
        otp_valid_upto = frappe.db.get_single_value('GeoLife Setting', 'otp_valid_upto')
        expiry_time = add_to_date(x_user[0].creation, seconds=180)

        if get_datetime(now()) > get_datetime(expiry_time):
            frappe.local.response["message"] = {
                "status": False,
                "message": "Time Out, Your OTP Expired"
            }
            return

    if not x_user:
        frappe.local.response["message"] = {
            "status": False,
            "message": "Invalid Otp, Please try again with correct otp"
        }
        return

    user_email = ""
    
    if x_user[0].otp == otp:

        user_exist = frappe.db.count("User",{'mobile_no': mobile_no})

        if user_exist > 0:

            userm = frappe.db.get_all('User', filters={'mobile_no': mobile_no}, fields=['*'])
            user_email = userm[0].name

            user_image = get_doctype_images('User', user_email)
            _user_image =[]
            
            if user_image:
                _user_image = user_image[0]['image']
                userm[0].images = _user_image

            api_key, api_secret = generate_keys(user_email)
            geomitra_data = frappe.db.get_all('Geo Mitra', filters={'linked_user': user_email}, fields=['*'])
            frappe.local.response["message"] = {
                "status": True,
                "message": "User Already Exists",
                "data":{
                "api_key": api_key,
                "api_secret": api_secret,
                "geomitra_data":geomitra_data,
                "first_name": userm[0].first_name,
                "last_name": userm[0].last_name,
                "mobile_no": userm[0].mobile_no,
                "email_id": userm[0].email,
                "role": userm[0].user_type
            }
            }
            return
            

        frappe.local.response["message"] = {
            "status": False,
            "message": "User Not Exists",
        }

def get_doctype_images(doctype, docname):
    attachments = frappe.get_all("File", fields=["attached_to_name", "file_name", "file_url", "is_private"], filters={
                                 "attached_to_name": docname, "attached_to_doctype": doctype})
    resp = []
    for attachment in attachments:
        # file_path = site_path + attachment["file_url"]
        x = get_files_path(attachment['file_name'], is_private=1)
        with open(x, "rb") as f:
            # encoded_string = base64.b64encode(image_file.read())
            img_content = f.read()
            img_base64 = base64.b64encode(img_content).decode()
            img_base64 = 'data:image/jpeg;base64,' + img_base64
        resp.append({"image": img_base64})

    return resp

def ng_write_file(data, filename, docname, doctype):
    try:
        filename_ext = f'/home/frappe-sonuarya/frappe-bench/sites/geolife_agritech/private/files/{filename}.png'
        base64data = data.replace('data:image/jpeg;base64,', '')
        imgdata = base64.b64decode(base64data)
        with open(filename_ext, 'wb') as file:
            file.write(imgdata)

        doc = frappe.get_doc(
            {
                "file_name": f'{filename}.png',
                "is_private": 1,
                "file_url": f'/private/files/{filename}.png',
                "attached_to_doctype": doctype,
                "attached_to_name": docname,
                "doctype": "File",
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        return doc.file_url

    except Exception as e:
        return e

@frappe.whitelist()
def crop_seminar():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "status": False,
            "message": "Unauthorised Access",
        }
        return

    if frappe.request.method =="GET":
        home_data = frappe.db.get_list("Crop Seminar", fields=["*"])
        frappe.response["message"] = {
            "status":True,
            "message": "",
            "data" : home_data
        }
        return
    
    elif frappe.request.method == "POST":
        Crop_data = frappe.request.json
        # if Crop_data['image']:
        #     ng_write_file(Crop_data['image'], 'demo.jpg', "", "Pet")
        crop = frappe.get_doc({
            "doctype":"Crop Seminar",
            "village": Crop_data['village'],
            "seminar_date": Crop_data['seminar_date'],
            "seminar_time": Crop_data['seminar_time'],
            "venue": Crop_data['venue'],
            "speeker_name": Crop_data['speeker_name'],
            "mobile_no": Crop_data['mobile_no'],
            "message": Crop_data['message'],
            "bk_center": Crop_data['bk_center'],
            "geo_mitra":_data['geomitra']

        })
        crop.insert()
        if Crop_data['image']:
            data = Crop_data['image']
            filename = Crop_data['pet_name']
            docname = crop.name
            doctype = "Crop Seminar"
            image = ng_write_file(data, filename, docname, doctype)

            crop.image = image
        crop.save()
        frappe.db.commit()

        frappe.response["message"] = {
            "status":True,
            "message": "Crop Seminar Added Successfully",
        }
        return

    elif frappe.request.method == "PUT":
        Crop_data = frappe.request.json
        crop = frappe.get_doc('Crop Seminar', Crop_data['name'])

        if Crop_data['crop_seminar_attendance']:
            crop.crop_seminar_attendance = Crop_data['crop_seminar_attendance']
            crop.crop_seminar_attendance = []
            for itm in Crop_data['crop_seminar_attendance'] :
                crop.append("crop_seminar_attendance",itm)
            
        if Crop_data['upload_photos']:
            crop.upload_photos = []
            for itm in Crop_data['upload_photos'] :
                crop.append("upload_photos",itm)
            # crop.upload_photos = Crop_data['upload_photos']
       
        # if Crop_data['image']:
        #     data = Crop_data['image']
        #     filename = Crop_data['pet_name']
        #     docname = Crop_data['name']
        #     doctype = "Pet"
        #     image = ng_write_file(data, filename, docname, doctype)
        #     crop.image = image

        crop.save(ignore_permissions=True)
        frappe.response["message"] = {
            "status":True,
            "message": "Crop Seminar Details Updated Successfully",
        }
        
        return

@frappe.whitelist(allow_guest=True)
def activity_list():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "status": False,
            "message": "Unauthorised Access",
        }
        return

    if frappe.request.method =="GET":
        home_data = frappe.db.get_list("Daily Activity", fields=["posting_date","activity_name","activity_type","notes"])
        frappe.response["message"] = {
            "status":True,
            "message": "",
            "data" : home_data
        }
        return
    
    elif frappe.request.method == "POST":
        _data = frappe.request.json
        # if Crop_data['image']:
        #     ng_write_file(Crop_data['image'], 'demo.jpg', "", "Pet")
        doc = frappe.get_doc({
            "doctype":"Daily Activity",
            "posting_date": frappe.utils.nowdate(),
            "activity_name": _data['activity_name'],
            "activity_type": _data['activity_type'],
            "notes": _data['notes'],
            "geo_mitra":_data['geomitra']

        })
        doc.insert()
        if _data['image']:
            data = _data['image']
            filename = doc.name
            docname = doc.name
            doctype = "Daily Activity"
            image = ng_write_file(data, filename, docname, doctype)

            doc.image = image
        doc.save()
        frappe.db.commit()

        frappe.response["message"] = {
            "status":True,
            "message": "Daily Activity Added Successfully",
        }
        return

@frappe.whitelist(allow_guest=True)
def activity_type():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "status": False,
            "message": "Unauthorised Access",
        }
        return

    if frappe.request.method =="GET":
        home_data = frappe.db.get_list("Activity Type", fields=["activity_type","name"])
        frappe.response["message"] = {
            "status":True,
            "message": "",
            "data" : home_data
        }
        return
    
@frappe.whitelist(allow_guest=True)
def expenses():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "status": False,
            "message": "Unauthorised Access",
        }
        return

    if frappe.request.method =="GET":
        home_data = frappe.db.get_list("Geo Expenses", fields=["posting_date","expense_type","amount","against_expense","notes"])
        frappe.response["message"] = {
            "status":True,
            "message": "",
            "data" : home_data
        }
        return
    
    elif frappe.request.method == "POST":
        _data = frappe.request.json
        doc = frappe.get_doc({
            "doctype":"Geo Expenses",
            "posting_date": frappe.utils.nowdate(),
            "expense_type": _data['expense_type'],
            "amount": _data['amount'],
            "against_expense": _data['against_expense'],
            "notes": _data['notes'],
            "geo_mitra":_data['geomitra']

        })
        doc.insert()
        if _data['image']:
            data = _data['image']
            filename = doc.name
            docname = doc.name
            doctype = "Geo Expenses"
            image = ng_write_file(data, filename, docname, doctype)

            doc.image = image
        doc.save()
        frappe.db.commit()

        frappe.response["message"] = {
            "status":True,
            "message": "Expensey Added Successfully",
        }
        return
    
@frappe.whitelist(allow_guest=True)
def whatsapp_to_farmer():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "status": False,
            "message": "Unauthorised Access",
        }
        return

    if frappe.request.method =="GET":
        home_data = frappe.db.get_list("Whatsapp Templates", fields=["*"])
        frappe.response["message"] = {
            "status":True,
            "message": "",
            "data" : home_data
        }
        return

@frappe.whitelist()
def door_to_door_awareness():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "status": False,
            "message": "Unauthorised Access",
        }
        return

    elif frappe.request.method == "POST":
        _data = frappe.request.json
        doc = frappe.get_doc({
            "doctype":"Door To Door Visit",
            # "posting_date": frappe.utils.nowdate(),
            # "employee_location": _data['location'],
            "notes": _data['notes'],
            "geo_mitra":_data['geomitra']

        })
        doc.insert()
        if _data['image']:
            data = _data['image']
            filename = doc.name
            docname = doc.name
            doctype = "Door To Door Visit"
            image = ng_write_file(data, filename, docname, doctype)

            doc.image = image
        doc.save()
        frappe.db.commit()

        frappe.response["message"] = {
            "status":True,
            "message": "Report Added Successfully",
        }
        return

@frappe.whitelist(allow_guest=True)
def sticker_pasting():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "status": False,
            "message": "Unauthorised Access",
        }
        return

    elif frappe.request.method == "POST":
        _data = frappe.request.json
        doc = frappe.get_doc({
            "doctype":"Sticker Pasting",
            # "posting_date": frappe.utils.nowdate(),
            # "employ_location": _data['location'],
            "notes": _data['notes'],
            "geo_mitra":_data['geomitra']

        })
        doc.insert()
        if _data['image']:
            data = _data['image']
            filename = doc.name
            docname = doc.name
            doctype = "Sticker Pasting"
            image = ng_write_file(data, filename, docname, doctype)
            doc.image = image

        doc.save()
        frappe.db.commit()

        frappe.response["message"] = {
            "status":True,
            "message": "Report Added Successfully",
        }
        return

@frappe.whitelist(allow_guest=True)
def raise_crop_alert():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "status": False,
            "message": "Unauthorised Access",
        }
        return

    elif frappe.request.method == "POST":
        _data = frappe.request.json
        doc = frappe.get_doc({
            "doctype":"Crop Alert",
            # "posting_date": frappe.utils.nowdate(),
            # "employ_location": _data['location'],
            "notes": _data['notes'],
            "geo_mitra":_data['geomitra']
        })
        doc.insert()
        if _data['image']:
            data = _data['image']
            filename = doc.name
            docname = doc.name
            doctype = "Crop Alert"
            image = ng_write_file(data, filename, docname, doctype)

        doc.image = image
        doc.save()
        frappe.db.commit()

        frappe.response["message"] = {
            "status":True,
            "message": "Report Added Successfully",
        }
        return