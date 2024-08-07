from flask import Flask, Response, jsonify, request
from flask_cors import CORS  # Import CORS
from download_service import DownloadService
from send_mails import EmailService
app = Flask(__name__)
CORS(app)
# Initialize download service
USERNAME = "mehdi.chebbi@esprit.tn"
PASSWORD = "AZEqsdwxc123."
CLIENT_ID = "cdse-public"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

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

if __name__ == '__main__':
    app.run(debug=True)
