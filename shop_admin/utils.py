import jwt
import logging
import os
import platform
import shutil
import subprocess
from functools import wraps
from typing import Dict, Optional
from pathlib import Path
from django.http import JsonResponse
from anand_mobiles.settings import SECRET_KEY
import cloudinary
from anand_mobiles.settings import CLOUDINARY_URL
import cloudinary.uploader
import io
from django.template.loader import render_to_string
import pdfkit
from datetime import datetime
import uuid

# Using only pdfkit for PDF generation
WEASYPRINT_AVAILABLE = False

# Set up logger for admin authentication
logger = logging.getLogger(__name__)

class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors"""
    pass

def find_wkhtmltopdf_path():
    """
    Dynamically find wkhtmltopdf executable path across different platforms.
    
    Returns:
        str: Path to wkhtmltopdf executable, or None if not found
    """
    # Common paths to check
    common_paths = []
    
    if platform.system() == "Windows":
        common_paths = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\wkhtmltopdf\bin\wkhtmltopdf.exe",
            "wkhtmltopdf.exe"
        ]
    else:  # Linux/Unix/macOS
        common_paths = [
            "/usr/bin/wkhtmltopdf",
            "/usr/local/bin/wkhtmltopdf",
            "/opt/wkhtmltopdf/bin/wkhtmltopdf",
            "wkhtmltopdf"
        ]
    
    # Check if wkhtmltopdf is available in PATH
    try:
        which_result = shutil.which("wkhtmltopdf")
        if which_result:
            logger.info(f"Found wkhtmltopdf in PATH: {which_result}")
            return which_result
    except Exception as e:
        logger.debug(f"Error checking PATH for wkhtmltopdf: {e}")
    
    # Check common installation paths
    for path in common_paths:
        if os.path.exists(path):
            logger.info(f"Found wkhtmltopdf at: {path}")
            return path
    
    logger.warning("wkhtmltopdf not found in any common locations")
    return None

def get_wkhtmltopdf_config():
    """Get wkhtmltopdf configuration with automatic path detection"""
    wkhtmltopdf_path = find_wkhtmltopdf_path()
    
    if wkhtmltopdf_path:
        try:
            return pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        except Exception as e:
            logger.warning(f"Failed to create pdfkit configuration: {e}")
            return None
    else:
        logger.warning("wkhtmltopdf not found, PDF generation may fail")
        return None

def get_pdf_options() -> Dict:
    """Get default PDF generation options optimized for wkhtmltopdf"""
    return {
        "page-size": "A4",
        "margin-top": "10mm",
        "margin-right": "10mm",
        "margin-bottom": "10mm", 
        "margin-left": "10mm",
        "encoding": "UTF-8",
        "no-outline": None,
        "enable-local-file-access": None,
        "disable-smart-shrinking": None,
        "print-media-type": None,
        "dpi": "96",
        "image-quality": "100",
        "enable-external-links": None,
        "enable-internal-links": None,
        "images": None,
        "quiet": None,
        "orientation": "Portrait",
        "disable-javascript": None,
        "load-error-handling": "ignore",
        "load-media-error-handling": "ignore",
        "minimum-font-size": "10",
        "page-height": "297mm",
        "page-width": "210mm"
    }

def admin_required(view_func):
    """
    Decorator that validates admin JWT tokens from the Authorization header.
    
    Expected format: Authorization: Bearer <admin_token>
    
    On success: Adds request.admin (username) and request.admin_payload (full JWT payload)
    On failure: Returns 401 response with specific error message
    
    Compatible with frontend admin API interceptors that handle 401 responses
    for automatic token cleanup and re-authentication.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get the authorization header
        auth_header = request.headers.get('Authorization')
        # Check for missing or malformed authorization header
        if not auth_header:
            logger.warning(f"Admin access attempt without authorization header from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authorization header required',
                'code': 'AUTH_HEADER_MISSING'
            }, status=401)
        
        if not auth_header.startswith('Bearer '):
            logger.warning(f"Admin access attempt with invalid authorization format from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Invalid authorization format. Expected: Bearer <token>',
                'code': 'AUTH_FORMAT_INVALID'
            }, status=401)
        
        # Extract the token
        try:
            token = auth_header.split(' ')[1]
            if not token.strip():
                raise IndexError("Empty token")
        except IndexError:
            logger.warning(f"Admin access attempt with empty token from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authorization token is empty',
                'code': 'TOKEN_EMPTY'
            }, status=401)
        
        try:
            # Verify and decode the JWT token
            payload = jwt.decode(token,SECRET_KEY, algorithms=['HS256'])
            
            # Validate required fields in token
            username = payload.get('username')
            if not username:
                logger.warning(f"Admin token missing username field from {request.META.get('REMOTE_ADDR')}")
                return JsonResponse({
                    'error': 'Invalid token: missing username',
                    'code': 'TOKEN_INVALID_PAYLOAD'
                }, status=401)
            
            # Add admin info to request object for use in views
            request.admin = username
            request.admin_payload = payload
            
            logger.info(f"Admin '{username}' authenticated successfully for {request.method} {request.path}")
            
            # Continue to the protected view
            return view_func(request, *args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            logger.info(f"Admin access attempt with expired token from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authentication token has expired',
                'code': 'TOKEN_EXPIRED'
            }, status=401)
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Admin access attempt with invalid token from {request.META.get('REMOTE_ADDR')}: {str(e)}")
            return JsonResponse({
                'error': 'Invalid authentication token',
                'code': 'TOKEN_INVALID'
            }, status=401)
            
        except Exception as e:
            logger.error(f"Unexpected authentication error from {request.META.get('REMOTE_ADDR')}: {str(e)}")
            return JsonResponse({
                'error': 'Authentication service error',
                'code': 'AUTH_SERVICE_ERROR'
            }, status=401)
    
    return wrapper

def upload_image_to_cloudinary_util(image_file, folder_name="shop_images"):
    """
    Uploads an image file to Cloudinary and returns its secure URL.

    Args:
        image_file: The image file object to upload (e.g., request.FILES['image']).
        folder_name (str): The name of the folder in Cloudinary to upload the image to.

    Returns:
        str: The secure URL of the uploaded image, or None if upload fails.
    """
    if not image_file:
        logger.error("No image file provided for Cloudinary upload.")
        return None

    try:
        # Configure Cloudinary using CLOUDINARY_URL from settings.py
        if CLOUDINARY_URL:
            cloudinary.config(cloudinary_url=CLOUDINARY_URL, secure=True)
        else:
            logger.error("CLOUDINARY_URL is not set in settings.")
            return None

        upload_result = cloudinary.uploader.upload(
            image_file,
            folder=folder_name,
            # Additional upload options can be added here
        )
        
        secure_url = upload_result.get('secure_url')
        
        if secure_url:
            logger.info(f"Image uploaded successfully to Cloudinary: {secure_url}")
            print('secure url', secure_url)
            return secure_url
        else:
            logger.error("Failed to upload image to Cloudinary. No secure_url in response.")
            return None
    except Exception as e:
        logger.error(f"Error uploading image to Cloudinary: {str(e)}")
        return None

def generate_invoice_pdf(invoice_data):
    """
    Generates a PDF invoice from HTML template using the provided invoice data.
    Uses pdfkit with wkhtmltopdf for PDF generation.
    
    Args:
        invoice_data (dict): Dictionary containing invoice details
        
    Returns:
        io.BytesIO: PDF file buffer, or None if generation fails
    """
    logger.info(f"Starting PDF generation for order {invoice_data.get('order_id')}")
    
    try:
        logger.info("Attempting PDF generation with pdfkit")
        
        # Prepare context for template
        context = {
            'logo_url': 'https://res.cloudinary.com/dm23rhuct/image/upload/v1749542263/shop_logo/ao5kavrkh8m4mcdvi92h.jpg',
            'invoice_id': invoice_data.get('invoice_id'),
            'order_id': invoice_data.get('order_id'),
            'date': invoice_data.get('date'),
            'user_name': invoice_data.get('user_name'),
            'user_email': invoice_data.get('user_email'),
            'shipping_address': invoice_data.get('shipping_address'),
            'order_items': invoice_data.get('order_items', []),
            'subtotal': invoice_data.get('subtotal', 0),
            'shipping_cost': invoice_data.get('shipping_cost', 0),
            'tax_rate_percentage': invoice_data.get('tax_rate_percentage', 18),
            'tax_amount': invoice_data.get('tax_amount', 0),
            'total_amount': invoice_data.get('total_amount', 0),
            'current_year': datetime.now().year
        }
          # Render HTML template
        try:
            html_string = render_to_string('invoice_template.html', context)
            logger.info("HTML template rendered successfully")
            
            # Debug: Log a sample of the HTML content (first 500 characters)
            logger.debug(f"HTML content sample: {html_string[:500]}...")
            
        except Exception as template_error:
            logger.error(f"Failed to render HTML template: {str(template_error)}")
            raise PDFGenerationError(f"Template rendering failed: {str(template_error)}")
        
        # Try with configuration first
        config = get_wkhtmltopdf_config()
        pdf_options = get_pdf_options()
        
        pdf_bytes = None
        
        if config:
            try:
                logger.info("Trying pdfkit with custom configuration")
                pdf_bytes = pdfkit.from_string(
                    html_string,
                    False,  # Don't write to file, return bytes
                    options=pdf_options,
                    configuration=config,
                )
                
                if pdf_bytes and isinstance(pdf_bytes, bytes) and len(pdf_bytes) > 100:
                    logger.info(f"PDF generated with configuration. Size: {len(pdf_bytes)} bytes")
                else:
                    logger.warning("PDF generation with configuration returned invalid data")
                    pdf_bytes = None
                    
            except Exception as e:
                logger.warning(f"pdfkit with configuration failed: {str(e)}")
                pdf_bytes = None
        
        # Try without configuration (system PATH) if previous method failed
        if not pdf_bytes:
            try:
                logger.info("Trying pdfkit without custom configuration")
                basic_options = {
                    "page-size": "A4",
                    "margin-top": "15mm",
                    "margin-right": "15mm", 
                    "margin-bottom": "15mm",
                    "margin-left": "15mm",
                    "encoding": "UTF-8",
                    "no-outline": None,
                    "print-media-type": True,
                    "quiet": None,
                    "disable-smart-shrinking": True,
                }
                
                pdf_bytes = pdfkit.from_string(
                    html_string,
                    False,
                    options=basic_options
                )
                
                if pdf_bytes and isinstance(pdf_bytes, bytes) and len(pdf_bytes) > 100:
                    logger.info(f"PDF generated with basic options. Size: {len(pdf_bytes)} bytes")
                else:
                    logger.warning("PDF generation with basic options returned invalid data")
                    pdf_bytes = None
                    
            except Exception as fallback_error:
                logger.error(f"Basic pdfkit generation also failed: {str(fallback_error)}")
                pdf_bytes = None
        
        # Validate and return PDF if successful
        if pdf_bytes and isinstance(pdf_bytes, bytes) and len(pdf_bytes) > 100:
            # Verify it's a valid PDF
            if not pdf_bytes.startswith(b'%PDF'):
                logger.error("Generated data is not a valid PDF - missing PDF signature")
                raise PDFGenerationError("Generated PDF data is invalid")
            
            pdf_buffer = io.BytesIO(pdf_bytes)
            pdf_buffer.seek(0)
            logger.info(f"Invoice PDF generated successfully for order {invoice_data.get('order_id')} - Size: {len(pdf_bytes)} bytes")
            
            # Save PDF to disk for debugging
            save_pdf_to_disk_debug(pdf_buffer, filename="debug_invoice.pdf")
            
            return pdf_buffer
        else:
            logger.error("All PDF generation methods returned invalid data")
            raise PDFGenerationError("Failed to generate valid PDF data")
        
    except Exception as e:
        logger.error(f"Error in pdfkit PDF generation: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
    
    # All PDF generation methods failed
    logger.error("PDF generation failed")
    raise PDFGenerationError("Failed to generate PDF with pdfkit. Please ensure wkhtmltopdf is installed.")

def upload_pdf_to_cloudinary_util(pdf_buffer, filename, folder_name="invoices"):
    """
    Uploads a PDF file buffer to Cloudinary and returns its secure URL.
    Tries multiple upload methods for better reliability.
    
    Args:
        pdf_buffer (io.BytesIO): The PDF file buffer to upload
        filename (str): The filename for the uploaded PDF
        folder_name (str): The folder name in Cloudinary
        
    Returns:
        str: The secure URL of the uploaded PDF, or None if upload fails
    """
    if not pdf_buffer:
        logger.error("No PDF buffer provided for Cloudinary upload.")
        return None
        
    try:
        # Configure Cloudinary using CLOUDINARY_URL from settings.py
        if CLOUDINARY_URL:
            cloudinary.config(cloudinary_url=CLOUDINARY_URL, secure=True)
        else:
            logger.error("CLOUDINARY_URL is not set in settings.")
            return None
        
        # Ensure buffer is at the beginning
        pdf_buffer.seek(0)
        
        # Get the raw bytes from the buffer
        pdf_bytes = pdf_buffer.getvalue()
        
        # Validate PDF bytes
        if not pdf_bytes or len(pdf_bytes) < 100:
            logger.error(f"PDF buffer is too small or empty. Size: {len(pdf_bytes) if pdf_bytes else 0} bytes")
            return None
        
        # Check if it's a valid PDF (starts with PDF signature)
        if not pdf_bytes.startswith(b'%PDF'):
            logger.error("Buffer does not contain valid PDF data - missing PDF signature")
            return None
        
        logger.info(f"Uploading PDF to Cloudinary. Size: {len(pdf_bytes)} bytes, Filename: {filename}")
        
        # Method 1: Try direct BytesIO upload with 'raw' resource type
        try:
            # Create a new BytesIO object with the PDF data for upload
            upload_buffer = io.BytesIO(pdf_bytes)
            upload_buffer.seek(0)
            
            upload_result = cloudinary.uploader.upload(
                upload_buffer,
                resource_type="raw",  # Use 'raw' for PDF files instead of 'auto'
                folder=folder_name,
                public_id=filename,
                format="pdf",
                use_filename=True,
                unique_filename=False
            )
            
            secure_url = upload_result.get('secure_url')
            
            if secure_url:
                logger.info(f"PDF uploaded successfully to Cloudinary (method 1): {secure_url}")
                print('secure url (method 1)', secure_url)
                return secure_url
            else:
                logger.warning("Method 1 failed - no secure_url in response")
                
        except Exception as method1_error:
            logger.warning(f"Method 1 (direct BytesIO) failed: {str(method1_error)}")
        
        # Method 2: Try base64 upload as fallback
        try:
            logger.info("Trying base64 upload method as fallback")
            result = upload_pdf_to_cloudinary_base64(pdf_buffer, filename, folder_name)
            if result:
                return result
        except Exception as method2_error:
            logger.warning(f"Method 2 (base64) failed: {str(method2_error)}")
        
        # Method 3: Try with different resource type settings
        try:
            logger.info("Trying alternative upload settings")
            upload_buffer = io.BytesIO(pdf_bytes)
            upload_buffer.seek(0)
            
            upload_result = cloudinary.uploader.upload(
                upload_buffer,
                resource_type="auto",  # Let Cloudinary auto-detect
                folder=folder_name,
                public_id=filename,
                use_filename=True,
                unique_filename=False,
                allowed_formats=["pdf"]
            )
            
            secure_url = upload_result.get('secure_url')
            
            if secure_url:
                logger.info(f"PDF uploaded successfully to Cloudinary (method 3): {secure_url}")
                print('secure url (method 3)', secure_url)
                return secure_url
                
        except Exception as method3_error:
            logger.warning(f"Method 3 (alternative settings) failed: {str(method3_error)}")
        
        # All methods failed
        logger.error("All upload methods failed")
        return None
            
    except Exception as e:
        logger.error(f"Error uploading PDF to Cloudinary: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return None

def upload_pdf_to_cloudinary_base64(pdf_buffer, filename, folder_name="invoices"):
    """
    Alternative method to upload PDF using base64 encoding as fallback.
    
    Args:
        pdf_buffer (io.BytesIO): The PDF file buffer to upload
        filename (str): The filename for the uploaded PDF
        folder_name (str): The folder name in Cloudinary
        
    Returns:
        str: The secure URL of the uploaded PDF, or None if upload fails
    """
    if not pdf_buffer:
        logger.error("No PDF buffer provided for base64 Cloudinary upload.")
        return None
        
    try:
        # Configure Cloudinary using CLOUDINARY_URL from settings.py
        if CLOUDINARY_URL:
            cloudinary.config(cloudinary_url=CLOUDINARY_URL, secure=True)
        else:
            logger.error("CLOUDINARY_URL is not set in settings.")
            return None
        
        # Ensure buffer is at the beginning
        pdf_buffer.seek(0)
        
        # Get the raw bytes from the buffer
        pdf_bytes = pdf_buffer.getvalue()
        
        # Validate PDF bytes
        if not pdf_bytes or len(pdf_bytes) < 100:
            logger.error(f"PDF buffer is too small or empty. Size: {len(pdf_bytes) if pdf_bytes else 0} bytes")
            return None
        
        # Check if it's a valid PDF (starts with PDF signature)
        if not pdf_bytes.startswith(b'%PDF'):
            logger.error("Buffer does not contain valid PDF data - missing PDF signature")
            return None
        
        logger.info(f"Uploading PDF to Cloudinary using base64 method. Size: {len(pdf_bytes)} bytes, Filename: {filename}")
        
        # Convert to base64
        import base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        data_uri = f"data:application/pdf;base64,{pdf_base64}"
        
        upload_result = cloudinary.uploader.upload(
            data_uri,
            resource_type="raw",
            folder=folder_name,
            public_id=filename,
            format="pdf",
            use_filename=True,
            unique_filename=False
        )
        
        secure_url = upload_result.get('secure_url')
        print('base64 secure url', secure_url)
        
        if secure_url:
            logger.info(f"PDF uploaded successfully to Cloudinary using base64: {secure_url}")
            return secure_url
        else:
            logger.error("Failed to upload PDF to Cloudinary using base64. No secure_url in response.")
            logger.error(f"Upload result: {upload_result}")
            return None
            
    except Exception as e:
        logger.error(f"Error uploading PDF to Cloudinary using base64: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return None

def create_invoice_data(order_data, user_data, order_items):
    """
    Creates invoice data dictionary from order and user information.
    
    Args:
        order_data (dict): Order information from Firestore
        user_data (dict): User information from Firestore
        order_items (list): List of order items with product details
        
    Returns:
        dict: Invoice data ready for PDF generation
    """
    try:
        # Generate unique invoice ID
        invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Calculate amounts
        subtotal = sum(item.get('total_item_price', 0) for item in order_items)
        shipping_cost = order_data.get('shipping_cost', 0)
        tax_rate_percentage = 18  # GST rate
        tax_amount = (subtotal + shipping_cost) * (tax_rate_percentage / 100)
        total_amount = subtotal + shipping_cost + tax_amount
        
        # Prepare shipping address
        shipping_address = order_data.get('shipping_address')
        
        invoice_data = {
            'invoice_id': invoice_id,
            'order_id': order_data.get('order_id', ''),
            'date': datetime.now().strftime('%B %d, %Y'),
            'user_name': user_data.get('full_name', user_data.get('name', 'Customer')),
            'user_email': user_data.get('email', ''),
            'shipping_address': shipping_address,
            'order_items': order_items,
            'subtotal': subtotal,
            'shipping_cost': shipping_cost,
            'tax_rate_percentage': tax_rate_percentage,
            'tax_amount': tax_amount,
            'total_amount': total_amount
        }
        
        return invoice_data
        
    except Exception as e:
        logger.error(f"Error creating invoice data: {str(e)}")
        return None

def save_invoice_to_firestore(db, user_id, invoice_data, pdf_url):
    """
    Saves invoice information to Firestore invoices collection.
    
    Args:
        db: Firestore database client
        user_id (str): User ID
        invoice_data (dict): Invoice data dictionary
        pdf_url (str): URL of the uploaded PDF
        
    Returns:
        str: Invoice document ID, or None if save fails
    """
    try:
        # Create invoice document
        invoice_doc = {
            'invoice_id': invoice_data.get('invoice_id'),
            'order_id': invoice_data.get('order_id'),
            'user_id': user_id,
            'user_name': invoice_data.get('user_name'),
            'user_email': invoice_data.get('user_email'),
            'pdf_url': pdf_url,
            'subtotal': invoice_data.get('subtotal'),
            'shipping_cost': invoice_data.get('shipping_cost'),
            'tax_amount': invoice_data.get('tax_amount'),
            'total_amount': invoice_data.get('total_amount'),
            'created_at': datetime.now(),
            'status': 'generated'
        }
        
        # Save to Firestore
        invoice_ref = db.collection('invoices').document(invoice_data.get('invoice_id'))
        invoice_ref.set(invoice_doc)
        
        # Also add reference to user's invoices subcollection
        user_invoice_ref = db.collection('users').document(user_id).collection('invoices').document(invoice_data.get('invoice_id'))
        user_invoice_ref.set({
            'invoice_id': invoice_data.get('invoice_id'),
            'order_id': invoice_data.get('order_id'),
            'pdf_url': pdf_url,
            'total_amount': invoice_data.get('total_amount'),
            'created_at': datetime.now()
        })
        
        logger.info(f"Invoice {invoice_data.get('invoice_id')} saved to Firestore successfully")
        return invoice_data.get('invoice_id')
        
    except Exception as e:
        logger.error(f"Error saving invoice to Firestore: {str(e)}")
        return None

def save_pdf_to_disk_debug(pdf_buffer, filename="debug_invoice.pdf"):
    """
    Saves PDF buffer to disk for debugging purposes.
    
    Args:
        pdf_buffer (io.BytesIO): The PDF buffer to save
        filename (str): The filename to save as
        
    Returns:
        str: The file path if saved successfully, None otherwise
    """
    try:
        import tempfile
        
        # Create a temporary file
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        # Ensure buffer is at the beginning
        pdf_buffer.seek(0)
        
        # Write buffer to file
        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        logger.info(f"Debug PDF saved to: {file_path}")
        print(f"Debug PDF saved to: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Failed to save debug PDF: {str(e)}")
        return None
