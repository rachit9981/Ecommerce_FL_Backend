import jwt
import logging
import os
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

# Set up logger for admin authentication
logger = logging.getLogger(__name__)

class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors"""
    pass

def get_wkhtmltopdf_config() -> pdfkit.configuration:
    """Get wkhtmltopdf configuration based on the operating system"""
    wkhtmltopdf_path = (
        r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
        if os.name == "nt"
        else r"/usr/bin/wkhtmltopdf"
    )
    return pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

def get_pdf_options() -> Dict:
    """Get default PDF generation options"""
    return {
        "page-size": "A4",
        "margin-top": "15mm",
        "margin-right": "15mm",
        "margin-bottom": "15mm",
        "margin-left": "15mm",
        "encoding": "UTF-8",
        "no-outline": None,
        "enable-local-file-access": None,
        "print-media-type": True,
        "enable-smart-shrinking": False,
        "dpi": "300",
        "load-error-handling": "ignore",
        "javascript-delay": "1000",
        "zoom": "1.0",
        "enable-external-links": True,
        "enable-internal-links": True,
        "images": True,
        "quiet": None,
        "orientation": "Portrait",
        "title": None,
        "disable-smart-shrinking": True,
        "page-width": "210mm",
        "page-height": "297mm",
        "image-quality": 100,
        "image-dpi": "300",
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
    
    Args:
        invoice_data (dict): Dictionary containing invoice details
        
    Returns:
        io.BytesIO: PDF file buffer, or None if generation fails
    """
    try:
        # Prepare context for template
        context = {
            'logo_url': 'https://res.cloudinary.com/your-cloud/image/upload/v1/static/logo.jpg',  # Update with actual logo URL
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
        html_string = render_to_string('invoice_template.html', context)
        
        # Generate PDF using pdfkit
        try:
            pdf_bytes = pdfkit.from_string(
                html_string,
                False,  # Don't write to file, return bytes
                options=get_pdf_options(),
                configuration=get_wkhtmltopdf_config(),
            )
            
            # Create PDF buffer from bytes
            pdf_buffer = io.BytesIO(pdf_bytes)
            pdf_buffer.seek(0)
            
            logger.info(f"Invoice PDF generated successfully for order {invoice_data.get('order_id')}")
            return pdf_buffer
            
        except OSError as e:
            # wkhtmltopdf not found, fallback to a simpler approach
            logger.warning(f"wkhtmltopdf not found, using fallback method: {str(e)}")
            
            # Try without configuration (system PATH)
            try:
                pdf_bytes = pdfkit.from_string(
                    html_string,
                    False,
                    options={
                        "page-size": "A4",
                        "margin-top": "15mm",
                        "margin-right": "15mm", 
                        "margin-bottom": "15mm",
                        "margin-left": "15mm",
                        "encoding": "UTF-8",
                        "no-outline": None,
                        "print-media-type": True,
                        "quiet": None,
                    }
                )
                
                pdf_buffer = io.BytesIO(pdf_bytes)
                pdf_buffer.seek(0)
                
                logger.info(f"Invoice PDF generated successfully (fallback) for order {invoice_data.get('order_id')}")
                return pdf_buffer
                
            except Exception as fallback_error:
                logger.error(f"Fallback PDF generation also failed: {str(fallback_error)}")
                raise PDFGenerationError(f"Failed to generate PDF: {str(fallback_error)}")
        
    except Exception as e:
        logger.error(f"Error generating invoice PDF: {str(e)}")
        return None

def upload_pdf_to_cloudinary_util(pdf_buffer, filename, folder_name="invoices"):
    """
    Uploads a PDF file buffer to Cloudinary and returns its secure URL.
    
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
            
        upload_result = cloudinary.uploader.upload(
            pdf_buffer,
            resource_type="auto",  # Auto-detect file type
            folder=folder_name,
            public_id=filename,
            format="pdf"
        )
        
        secure_url = upload_result.get('secure_url')
        print('secure url', secure_url)
        
        if secure_url:
            logger.info(f"PDF uploaded successfully to Cloudinary: {secure_url}")
            return secure_url
        else:
            logger.error("Failed to upload PDF to Cloudinary. No secure_url in response.")
            return None
            
    except Exception as e:
        logger.error(f"Error uploading PDF to Cloudinary: {str(e)}")
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
