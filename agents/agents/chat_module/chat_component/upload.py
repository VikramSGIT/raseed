import json
import requests

def upload_image_to_drive(image_path, access_token, filename=None, folder_id=None):
    """
    Upload an image to Google Drive using OAuth access token.

    Parameters:
    - image_path (str): Local path to the image file.
    - access_token (str): User's OAuth 2.0 access token.
    - filename (str): Optional custom name for the uploaded file.
    - folder_id (str): Optional folder ID to upload the image into.

    Returns:
    - dict: Metadata of the uploaded file or error message.
    """
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    metadata = {
        "name": filename or image_path.split('/')[-1],
        "mimeType": "image/jpeg"
    }

    if folder_id:
        metadata["parents"] = [folder_id]

    files = {
        "metadata": ("metadata", json.dumps(metadata), "application/json"),
        "file": open(image_path, "rb")
    }

    response = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        headers=headers,
        files=files
    )
    print(response.json())
    if response.status_code in [200, 201]:
        return response.json()
    else:
        return {"error": response.text}


upload_image_to_drive('/Users/rakshithhr/Downloads/download.jpeg',access_token="**")