import glob
import json
import os
import zipfile
import cv2
import time

from flask import Flask, Response, jsonify, request, abort,  stream_with_context, make_response
from flask_cors import CORS  # Import CORS
from download_service import DownloadService
from send_mails import EmailService

import matplotlib.colors as mcolors
from requests.exceptions import ChunkedEncodingError
from flask import Flask, jsonify, request
import requests
from PIL import Image
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
from flask_cors import CORS
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

import os
import glob
import rasterio
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.colors as colors



# NDVI calculation functions
def ndvi(red, nir):
    return ((nir - red) / (nir + red))

def create_custom_colormap(ramp):
    ramp_sorted = sorted(ramp)
    values, colors = zip(*ramp_sorted)
    norm = mcolors.Normalize(vmin=min(values), vmax=max(values))
    cmap = mcolors.LinearSegmentedColormap.from_list('custom_cmap', [(norm(val), color) for val, color in ramp_sorted])
    return cmap, norm

# Custom color ramp
ramp = [
    [-0.5, '#0c0c0c'], [-0.2, '#bfbfbf'], [-0.1, '#dbdbdb'],
    [0, '#eaeaea'], [0.025, '#fff9cc'], [0.05, '#ede8b5'],
    [0.075, '#ddd89b'], [0.1, '#ccc682'], [0.125, '#bcb76b'],
    [0.15, '#afc160'], [0.175, '#a3cc59'], [0.2, '#91bf51'],
    [0.25, '#7fb247'], [0.3, '#70a33f'], [0.35, '#609635'],
    [0.4, '#4f892d'], [0.45, '#3f7c23'], [0.5, '#306d1c'],
    [0.55, '#216011'], [0.6, '#0f540a'], [1, '#004400'],
]
cmap, norm = create_custom_colormap(ramp)





app = Flask(__name__)
CORS(app)
# Initialize download service
USERNAME = "mehdi.chebbi@esprit.tn"
PASSWORD = "AZEqsdwxc123."
CLIENT_ID = "cdse-public"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
download_status = {}
download_service = DownloadService(TOKEN_URL, USERNAME, PASSWORD, CLIENT_ID)

# Initialize email service
SMTP_SERVER = 'smtp.office365.com'  # SMTP server for Outlook
SMTP_PORT = 587                 # Replace with your SMTP port (e.g., 465 for SSL)
SMTP_USER = 'mehdino12@outlook.com'  # Replace with your email address
SMTP_PASSWORD = 'azeqsdwxc123'  # Replace with your email password or app-specific password
email_service = EmailService(SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD)

@app.route('/download/<string:product_id>', methods=['GET'])
def download_product(product_id):
    access_token = download_service.get_access_token()
    if not access_token:
        return jsonify({"error": "Failed to fetch access token."}), 500

    response = download_service.download_product(product_id, access_token)
    if response.status_code == 200:
        headers = {
            'Content-Disposition': f'attachment; filename="{product_id}.zip"'
        }
        return Response(response.iter_content(chunk_size=8192), headers=headers, content_type='application/octet-stream')
    else:
        return jsonify({"error": f"Failed to download file. Status code: {response.status_code}"}), response.status_code

@app.route('/download-on-server/<string:product_id>', methods=['GET'])
def download_on_server(product_id):
    access_token = download_service.get_access_token()
    if not access_token:
        abort(500, description="Failed to fetch access token.")

    zip_file_path = os.path.join(r'C:\Users\mehdi\Desktop\images-oss\img', f"{product_id}.zip")
    os.makedirs(os.path.dirname(zip_file_path), exist_ok=True)

    try:
        response = download_service.download_product(product_id, access_token)
        if response.status_code == 200:
            total_size = int(response.headers.get('content-length', 0))
            chunk_size = 8192
            start_time = time.time()
            downloaded_size = 0
            download_status[product_id] = 'downloading'

            def generate():
                nonlocal downloaded_size
                try:
                    with open(zip_file_path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if download_status.get(product_id) == 'cancelled':
                                break
                            file.write(chunk)
                            downloaded_size += len(chunk)
                            elapsed_time = time.time() - start_time
                            estimated_total_time = (elapsed_time / downloaded_size) * total_size
                            remaining_time = estimated_total_time - elapsed_time
                            progress = {
                                'downloaded': downloaded_size,
                                'total': total_size,
                                'remaining_time': remaining_time
                            }
                            yield f"data: {json.dumps(progress)}\n\n"
                except ChunkedEncodingError:
                    yield "data: {\"status\": \"error\", \"message\": \"Download interrupted.\"}\n\n"
                finally:
                    if download_status.get(product_id) != 'cancelled':
                        try:
                            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                                for member in zip_ref.namelist():
                                    zip_ref.extract(member, path=os.path.dirname(zip_file_path))
                            os.remove(zip_file_path)
                            yield "data: {\"status\": \"complete\"}\n\n"
                        except Exception as e:
                            yield f"data: {{\"status\": \"error\", \"message\": \"{str(e)}\"}}\n\n"
                    else:
                        os.remove(zip_file_path)
                        yield "data: {\"status\": \"cancelled\"}\n\n"
                    download_status.pop(product_id, None)

            return Response(stream_with_context(generate()), content_type='text/event-stream')

        else:
            abort(response.status_code, description="Failed to download file.")

    except Exception as e:
        abort(500, description=f"An error occurred: {str(e)}")

@app.route('/cancel-download/<string:product_id>', methods=['POST', 'GET'])
def cancel_download(product_id):
    if product_id in download_status:
        download_status[product_id] = 'cancelled'
        return make_response('', 200)  # No content, just the status code 200
    else:
        return make_response('', 404)  # No content, just the status code 404
@app.route('/send-email', methods=['POST'])
def send_email():
    data = request.json
    to_email = data.get('to', '')  # Default or from request
    subject = data.get('subject', 'No Subject')
    body = data.get('body', 'No Body')

    # Process the email sending logic
    if email_service.send_email(to_email, subject, body):
        return jsonify({"message": "Email sent successfully."}), 200
    else:
        return jsonify({"error": "Failed to send email."}), 500

@app.route('/send-email-page')
def send_email_page():
    return '''
        <!doctype html>
        <html>
        <head>
            <title>Send Email</title>
        </head>
        <body>
            <h1>Send Test Email</h1>
            <button onclick="sendEmail()">Send Email</button>
            <p id="response"></p>
            <script>
                function sendEmail() {
                    fetch('/send-email', { method: 'POST' })
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('response').innerText = data.message || data.error;
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            document.getElementById('response').innerText = 'An error occurred.';
                        });
                }
            </script>
        </body>
        </html>
    '''

@app.route('/contact', methods=['POST'])
def contact():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    subject = data.get('subject')
    message = data.get('message')

    # Process the data (e.g., send an email or save to a database)
    # For demonstration, we'll just print the data to the console
    print(f"Received contact form submission: {data}")

    return jsonify({"message": "Contact form submitted successfully."}), 200

# Default index route
@app.route('/')
def index():
    return '''
        <!doctype html>
        <html>
        <head>
            <title>Download Interface</title>
        </head>
        <body>
            <h1>Download File</h1>
            <button onclick="downloadFile()">Download</button>
            <script>
                function downloadFile() {
                    fetch('/download/a5ab498a-7b2f-4043-ae2a-f95f457e7b3b').then(response => {
                        if (response.ok) {
                            response.blob().then(blob => {
                                let url = window.URL.createObjectURL(blob);
                                let a = document.createElement('a');
                                a.href = url;
                                a.download = "image.zip";
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                            });
                        } else {
                            response.json().then(data => {
                                alert('Error: ' + data.error);
                            });
                        }
                    }).catch(error => console.error('Error:', error));
                }
            </script>
        </body>
        </html>
    '''
@app.route('/process-image', methods=['GET'])
def process_image():
    # Retrieve the 'text' parameter from the query string
    productName = request.args.get('imgName', '')
    print(f'Received text: {productName}')  # Print the text to the Flask server's command line

    base_path = fr'C:\Users\mehdi\Desktop\images-oss\img\{productName}\GRANULE'

    try:
        # Find the first directory under GRANULE
        granule_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
        if not granule_dirs:
            return jsonify({"error": "No directories found under GRANULE."}), 404

        # Use the first directory found
        granule_path = os.path.join(base_path, granule_dirs[0])
        R10_path = os.path.join(granule_path, 'IMG_DATA', 'R10m')

        # Search for the file with the pattern
        file_pattern = os.path.join(R10_path, '*_TCI_10m.jp2')
        matching_files = glob.glob(file_pattern)
        # Construct the input path
        output_path = fr'C:\Users\mehdi\Desktop\images-oss\{productName}.png'

        # Read the image
        img = cv2.imread(matching_files[0], cv2.IMREAD_UNCHANGED)
        if img is None:
            return jsonify({"error": "Failed to read the image from the input path."}), 400

        # Write the image to a .PNG file
        cv2.imwrite(output_path, img, [cv2.IMWRITE_PNG_COMPRESSION, 0])  # 0 means no compression

        return '', 204
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500




def compute_lai(nir, red):
    """Compute Leaf Area Index (LAI) from NIR and Red bands using an empirical model."""
    nir = nir.astype(np.float64)
    red = red.astype(np.float64)

    # Example model: Adjust the formula based on your specific model or empirical data
    # This is a placeholder; a real model should be based on actual research or data
    lai_array = (nir - red) / (nir + red)  # Placeholder formula for demonstration

    # Normalize the LAI array to be within a reasonable range (e.g., 0 to 5)
    lai_array = np.clip(lai_array, 0, 5)

    return lai_array

@app.route('/process-lai', methods=['GET'])
def process_lai():
    img_name = request.args.get('imgName', '')
    base_path = fr'C:\Users\mehdi\Desktop\images-oss\img\{img_name}\GRANULE'

    try:
        granule_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
        if not granule_dirs:
            return jsonify({"error": "No directories found under GRANULE."}), 404

        granule_path = os.path.join(base_path, granule_dirs[0])
        R10_path = os.path.join(granule_path, 'IMG_DATA', 'R10m')

        red_files = glob.glob(os.path.join(R10_path, '*B04_10m.jp2'))
        nir_files = glob.glob(os.path.join(R10_path, '*B08_10m.jp2'))

        if not red_files or not nir_files:
            return jsonify({"error": "One or both of the required band files are missing."}), 404

        with rasterio.open(red_files[0]) as red_src:
            red = red_src.read(1).astype(np.float64)

        with rasterio.open(nir_files[0]) as nir_src:
            nir = nir_src.read(1).astype(np.float64)

        lai_array = compute_lai(nir, red)

        # Normalize LAI array to 0-255 for grayscale image
        lai_array_normalized = 255 * (lai_array - np.min(lai_array)) / (np.max(lai_array) - np.min(lai_array))
        lai_array_normalized = lai_array_normalized.astype(np.uint8)

        # Convert to PIL image (grayscale mode)
        lai_image = Image.fromarray(lai_array_normalized, mode='L')

        # Save as PNG with minimal compression
        lai_image_filename = os.path.join(r'C:\Users\mehdi\Desktop\images-oss\LAI', f'{img_name}.png')
        lai_image.save(lai_image_filename, format='PNG', compress_level=0)

        return jsonify({
            "message": "LAI processing completed.",
            "lai_file": lai_image_filename
        }), 200
    except FileNotFoundError as e:
        return jsonify({"error": f"File not found: {str(e)}"}), 404
    except rasterio.errors.RasterioError as e:
        return jsonify({"error": f"Rasterio error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@app.route('/process-ndvi', methods=['GET'])
def process_ndvi():
    img_name = request.args.get('imgName', '')
    base_path = fr'C:\Users\mehdi\Desktop\images-oss\img\{img_name}\GRANULE'

    print(f'Processing NDVI for image: {img_name}')
    print(f'Base path: {base_path}')

    try:
        # Find the first directory under GRANULE
        granule_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
        if not granule_dirs:
            print('No directories found under GRANULE.')
            return jsonify({"error": "No directories found under GRANULE."}), 404

        granule_path = os.path.join(base_path, granule_dirs[0])
        print(f'Granule path: {granule_path}')

        R10_path = os.path.join(granule_path, 'IMG_DATA', 'R10m')
        print(f'R10 path: {R10_path}')

        red_file = glob.glob(os.path.join(R10_path, '*B04_10m.jp2'))
        nir_file = glob.glob(os.path.join(R10_path, '*B08_10m.jp2'))

        print(f'Red band files found: {red_file}')
        print(f'NIR band files found: {nir_file}')

        if not red_file or not nir_file:
            print('One or both of the required band files are missing.')
            return jsonify({"error": "One or both of the required band files are missing."}), 404

        with rasterio.open(red_file[0]) as red_src:
            red = red_src.read(1).astype(np.float64)
            transform = red_src.transform
            projection = red_src.crs

        with rasterio.open(nir_file[0]) as nir_src:
            nir = nir_src.read(1).astype(np.float64)

        print('Read red and NIR bands successfully.')

        # NDVI calculation
        ndvi_array = ndvi(red, nir)
        print('NDVI calculation completed.')

        # Apply color ramp
        ndvi_colored = (cmap(norm(ndvi_array))[:, :, :3] * 255).astype(np.uint8)

        # Save NDVI with color ramp as GeoTIFF
        ndvi_colored_filename = os.path.join(r'C:\Users\mehdi\Desktop\images-oss\NDVI', f'{img_name}_NDVI_colored.png')
        print(f'Saving NDVI colored file as: {ndvi_colored_filename}')

        with rasterio.open(
                ndvi_colored_filename, 'w',
                driver='GTiff',
                height=ndvi_colored.shape[0],
                width=ndvi_colored.shape[1],
                count=3,
                dtype='uint8',
                crs=projection,
                transform=transform
        ) as dst:
            dst.write(ndvi_colored[:, :, 0], 1)
            dst.write(ndvi_colored[:, :, 1], 2)
            dst.write(ndvi_colored[:, :, 2], 3)

        # Convert the NDVI array to an image
        ndvi_image = Image.fromarray(ndvi_colored)

        # Save as PNG with minimal compression
        ndvi_colored_filename_png = os.path.join(r'C:\Users\mehdi\Desktop\images-oss\NDVI', f'{img_name}.png')
        print(f'Saving NDVI PNG file as: {ndvi_colored_filename_png}')
        ndvi_image.save(ndvi_colored_filename_png, format='PNG', compress_level=0)

        print('NDVI processing completed successfully.')

        return jsonify({
            "message": "NDVI processing completed.",
            "ndvi_colored_file": ndvi_colored_filename_png
        }), 200
    except Exception as e:
        print(f'An error occurred: {str(e)}')
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500




def msavi(red, nir):
    numerator = 2 * nir + 1
    denominator = 2
    discriminant = (2 * nir + 1) ** 2 - 8 * (nir - red)
    msavi = (numerator - np.sqrt(discriminant)) / denominator
    return msavi

@app.route('/process-msavi', methods=['GET'])
def process_msavi():
    img_name = request.args.get('imgName', '')
    base_path = fr'C:\Users\mehdi\Desktop\images-oss\img\{img_name}\GRANULE'

    try:
        granule_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
        if not granule_dirs:
            return jsonify({"error": "No directories found under GRANULE."}), 404

        granule_path = os.path.join(base_path, granule_dirs[0])
        R10_path = os.path.join(granule_path, 'IMG_DATA', 'R10m')

        red_file = glob.glob(os.path.join(R10_path, '*B04_10m.jp2'))
        nir_file = glob.glob(os.path.join(R10_path, '*B08_10m.jp2'))

        if not red_file or not nir_file:
            return jsonify({"error": "One or both of the required band files are missing."}), 404

        with rasterio.open(red_file[0]) as red_src:
            red = red_src.read(1).astype(np.float64)
            transform = red_src.transform
            projection = red_src.crs

        with rasterio.open(nir_file[0]) as nir_src:
            nir = nir_src.read(1).astype(np.float64)

        msavi_array = msavi(red, nir)
        norm = colors.Normalize(vmin=-1, vmax=1)
        cmap = plt.get_cmap('RdYlGn')

        msavi_colored = (cmap(norm(msavi_array))[:, :, :3] * 255).astype(np.uint8)

        msavi_image = Image.fromarray(msavi_colored)
        msavi_colored_filename = os.path.join(r'C:\Users\mehdi\Desktop\images-oss\MSAVI', f'{img_name}.png')
        msavi_image.save(msavi_colored_filename, format='PNG', compress_level=0)

        return jsonify({
            "message": "MSAVI processing completed.",
            "msavi_colored_file": msavi_colored_filename
        }), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


def msavi2(nir, red):
    """Compute the Modified Soil-Adjusted Vegetation Index (MSAVI2)."""
    nir = nir.astype(np.float64)
    red = red.astype(np.float64)
    numerator = 2 * nir + 1
    denominator = 2 * np.sqrt(numerator ** 2 - 8 * (nir - red))
    msavi2_array = (numerator - denominator) / 2
    return msavi2_array

@app.route('/process-msavi2', methods=['GET'])
def process_msavi2():
    img_name = request.args.get('imgName', '')
    base_path = fr'C:\Users\mehdi\Desktop\images-oss\img\{img_name}\GRANULE'

    try:
        granule_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
        if not granule_dirs:
            return jsonify({"error": "No directories found under GRANULE."}), 404

        granule_path = os.path.join(base_path, granule_dirs[0])
        R10_path = os.path.join(granule_path, 'IMG_DATA', 'R10m')

        red_files = glob.glob(os.path.join(R10_path, '*B04_10m.jp2'))
        nir_files = glob.glob(os.path.join(R10_path, '*B08_10m.jp2'))

        if not red_files or not nir_files:
            return jsonify({"error": "One or both of the required band files are missing."}), 404

        with rasterio.open(red_files[0]) as red_src:
            red = red_src.read(1).astype(np.float64)

        with rasterio.open(nir_files[0]) as nir_src:
            nir = nir_src.read(1).astype(np.float64)

        msavi2_array = msavi2(nir, red)

        # Normalize MSAVI2 array to 0-1 for colormap application
        msavi2_array_normalized = (msavi2_array - np.min(msavi2_array)) / (np.max(msavi2_array) - np.min(msavi2_array))

        # Apply colormap
        colormap = plt.get_cmap('YlGn')  # Using Yellow to Green colormap
        msavi2_colored = colormap(msavi2_array_normalized)

        # Convert to PIL image
        msavi2_colored_image = Image.fromarray((msavi2_colored[:, :, :3] * 255).astype(np.uint8))

        # Save as PNG with minimal compression
        msavi2_image_filename = os.path.join(r'C:\Users\mehdi\Desktop\images-oss\MSAVI2', f'{img_name}.png')
        msavi2_colored_image.save(msavi2_image_filename, format='PNG', compress_level=0)

        return jsonify({
            "message": "MSAVI2 processing completed.",
            "msavi2_file": msavi2_image_filename
        }), 200
    except FileNotFoundError as e:
        return jsonify({"error": f"File not found: {str(e)}"}), 404
    except rasterio.errors.RasterioError as e:
        return jsonify({"error": f"Rasterio error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


def savi(red, nir, L=0.5):
    numerator = (nir - red) * (1 + L)
    denominator = nir + red + L
    savi = numerator / denominator
    return savi

def create_custom_cmap():
    # Define the color ramp with fixed start (0) and end (1)
    color_ramp = [
        (0, '#0c0c0c'),
        (0.025, '#fff9cc'),
        (0.05, '#ede8b5'),
        (0.075, '#ddd89b'),
        (0.1, '#ccc682'),
        (0.125, '#bcb76b'),
        (0.15, '#afc160'),
        (0.175, '#a3cc59'),
        (0.2, '#91bf51'),
        (0.25, '#7fb247'),
        (0.3, '#70a33f'),
        (0.35, '#609635'),
        (0.4, '#4f892d'),
        (0.45, '#3f7c23'),
        (0.5, '#306d1c'),
        (0.55, '#216011'),
        (0.6, '#0f540a'),
        (1, '#004400')
    ]

    # Separate the color ramp into values and colors
    values, colors_hex = zip(*color_ramp)
    colors_rgb = [colors.hex2color(c) for c in colors_hex]

    # Create a colormap
    return mcolors.LinearSegmentedColormap.from_list('custom_cmap', list(zip(values, colors_rgb)))

@app.route('/process-savi', methods=['GET'])
def process_savi():
    img_name = request.args.get('imgName', '')
    base_path = fr'C:\Users\mehdi\Desktop\images-oss\img\{img_name}\GRANULE'

    try:
        granule_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
        if not granule_dirs:
            return jsonify({"error": "No directories found under GRANULE."}), 404

        granule_path = os.path.join(base_path, granule_dirs[0])
        R10_path = os.path.join(granule_path, 'IMG_DATA', 'R10m')

        red_file = glob.glob(os.path.join(R10_path, '*B04_10m.jp2'))
        nir_file = glob.glob(os.path.join(R10_path, '*B08_10m.jp2'))

        if not red_file or not nir_file:
            return jsonify({"error": "One or both of the required band files are missing."}), 404

        with rasterio.open(red_file[0]) as red_src:
            red = red_src.read(1).astype(np.float64)
            transform = red_src.transform
            projection = red_src.crs

        with rasterio.open(nir_file[0]) as nir_src:
            nir = nir_src.read(1).astype(np.float64)

        savi_array = savi(red, nir)
        custom_cmap = create_custom_cmap()
        norm = colors.Normalize(vmin=savi_array.min(), vmax=savi_array.max())

        savi_colored = (custom_cmap(norm(savi_array))[:, :, :3] * 255).astype(np.uint8)

        savi_image = Image.fromarray(savi_colored)
        savi_colored_filename = os.path.join(r'C:\Users\mehdi\Desktop\images-oss\SAVI', f'{img_name}.png')
        savi_image.save(savi_colored_filename, format='PNG', compress_level=0)

        return jsonify({
            "message": "SAVI processing completed.",
            "savi_colored_file": savi_colored_filename
        }), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


# Token management
TOKEN_URL = 'https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token'
CLIENT_ID = 'f3c6ad1d-d127-4fea-a630-2506b44545ce'
CLIENT_SECRET = 'rYSWPIU5FGjcZNAdv4Z0PYjLYhW9nj3Y'
token_expiry = datetime.now()  # Initially set to the current time

# Define a global variable to store the token
oauth_token = None

def get_access_token():
    global token_expiry, oauth_token

    client = BackendApplicationClient(client_id=CLIENT_ID)
    oauth = OAuth2Session(client=client)

    # If the token is expired or not set
    if oauth_token is None or datetime.now() >= token_expiry:
        # Fetch new token
        token = oauth.fetch_token(
            token_url=TOKEN_URL,
            client_secret=CLIENT_SECRET,
            include_client_id=True
        )
        oauth_token = token  # Store the fetched token globally
        token_expiry = datetime.now() + timedelta(seconds=token['expires_in'])  # Update expiry time
        return token['access_token']
    else:
        # Return existing token
        return oauth_token['access_token']

# Function to calculate mean NDVI
def calculate_mean_ndvi(image):
    np_image = np.array(image)
    ndvi_values = np_image[..., 0]  # Adjust the channel index if necessary
    normalized_ndvi_values = (ndvi_values / 255.0) * 2 - 1  # Scaling from 0-255 to -1 to 1
    mean_ndvi = np.mean(normalized_ndvi_values)
    return mean_ndvi

# Helper function to generate monthly date ranges over the past year
def generate_monthly_ranges():
    today = datetime.today()
    start_date = today.replace(day=1)  # Start of the current month
    end_date = today

    month_ranges = []

    for _ in range(12):
        # Calculate the end of the month
        month_end = start_date + timedelta(days=31)
        month_end = month_end.replace(day=1) - timedelta(days=1)

        # Adjust if it's the current month
        if month_end > end_date:
            month_end = end_date

        month_ranges.append((start_date.strftime('%Y-%m-%dT00:00:00Z'), month_end.strftime('%Y-%m-%dT23:59:59Z')))

        # Move to the previous month
        start_date = (start_date - timedelta(days=1)).replace(day=1)

    return list(reversed(month_ranges))

@app.route('/ndvi', methods=['POST'])
def ndvi_graph():
    # Get coordinates from the request
    data = request.json
    coords = data.get('coordinates')
    if not coords:
        return jsonify({"error": "Coordinates not provided"}), 400

    # Generate monthly date ranges over the past year
    month_ranges = generate_monthly_ranges()

    ndvi_results = {}

    for month_start, month_end in month_ranges:
        url = "https://services.sentinel-hub.com/api/v1/process"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_access_token()}"
        }
        request_data = {
            "input": {
                "bounds": {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": coords
                    }
                },
                "data": [
                    {
                        "dataFilter": {
                            "timeRange": {
                                "from": month_start,
                                "to": month_end
                            }
                        },
                        "type": "sentinel-2-l2a"
                    }
                ]
            },
            "output": {
                "width": 512,
                "height": 343.697,
                "responses": [
                    {
                        "identifier": "default",
                        "format": {
                            "type": "image/jpeg"
                        }
                    }
                ]
            },
            "evalscript": "//VERSION=3\nfunction setup() {\n   return {\n      input: [\"B04\", \"B08\", \"dataMask\"],\n      output: { bands: 4 }\n   };\n}\n\nconst ramp = [\n   [-0.5, 0x0c0c0c],\n   [-0.2, 0xbfbfbf],\n   [-0.1, 0xdbdbdb],\n   [0, 0xeaeaea],\n   [0.025, 0xfff9cc],\n   [0.05, 0xede8b5],\n   [0.075, 0xddd89b],\n   [0.1, 0xccc682],\n   [0.125, 0xbcb76b],\n   [0.15, 0xafc160],\n   [0.175, 0xa3cc59],\n   [0.2, 0x91bf51],\n   [0.25, 0x7fb247],\n   [0.3, 0x70a33f],\n   [0.35, 0x609635],\n   [0.4, 0x4f892d],\n   [0.45, 0x3f7c23],\n   [0.5, 0x306d1c],\n   [0.55, 0x216011],\n   [0.6, 0x0f540a],\n   [1, 0x004400],\n];\n\nconst visualizer = new ColorRampVisualizer(ramp);\n\nfunction evaluatePixel(samples) {\n   let ndvi = index(samples.B08, samples.B04);\n   let imgVals = visualizer.process(ndvi);\n   return imgVals.concat(samples.dataMask)\n}"
        }

        response = requests.post(url, headers=headers, json=request_data)

        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            mean_ndvi = calculate_mean_ndvi(image)
            ndvi_results[f"{month_start[:7]}"] = mean_ndvi  # Use year-month format as key
        else:
            ndvi_results[f"{month_start[:7]}"] = {
                "error": "Failed to retrieve image",
                "status_code": response.status_code,
                "response": response.text
            }

    return jsonify(ndvi_results)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
