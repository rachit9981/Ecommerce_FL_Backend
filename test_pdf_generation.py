"""
Test script for PDF generation functionality
Run this script to verify that PDF generation is working correctly
"""

import os
import sys
import django
from datetime import datetime

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anand_mobiles.settings')
django.setup()

from shop_admin.utils import generate_invoice_pdf, PDFGenerationError

def test_pdf_generation():
    """Test PDF generation with sample data"""
    
    # Sample invoice data
    sample_invoice_data = {
        'invoice_id': 'INV-20250615-TEST123',
        'order_id': 'ORD-TEST-001',
        'date': datetime.now().strftime('%B %d, %Y'),
        'user_name': 'John Doe',
        'user_email': 'john.doe@example.com',
        'shipping_address': {
            'street': '123 Test Street',
            'city': 'Test City',
            'state': 'Test State',
            'zip_code': '12345'
        },        'order_items': [
            {
                'name': 'iPhone 15 Pro',
                'brand': 'Apple',
                'model': '256GB, Space Black',
                'quantity': 1,
                'price_at_purchase': 99999.00,
                'total_item_price': 99999.00
            },
            {
                'name': 'AirPods Pro',
                'brand': 'Apple', 
                'model': '2nd Generation',
                'quantity': 2,
                'price_at_purchase': 24900.00,
                'total_item_price': 49800.00
            }
        ],
        'subtotal': 149799.00,
        'shipping_cost': 200.00,
        'tax_rate_percentage': 18,
        'tax_amount': 26999.82,
        'total_amount': 176998.82
    }
    
    print("Testing PDF generation...")
    print("=" * 50)
    
    try:
        # Test PDF generation
        pdf_buffer = generate_invoice_pdf(sample_invoice_data)
        
        if pdf_buffer:
            # Save test PDF to file
            test_filename = f"test_invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            with open(test_filename, 'wb') as f:
                f.write(pdf_buffer.getvalue())
            
            print(f"✓ PDF generation successful!")
            print(f"✓ Test PDF saved as: {test_filename}")
            print(f"✓ PDF size: {len(pdf_buffer.getvalue())} bytes")
            
            return True
            
        else:
            print("✗ PDF generation returned None")
            return False
            
    except PDFGenerationError as e:
        print(f"✗ PDF Generation Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def check_dependencies():
    """Check available PDF generation dependencies"""
    
    print("Checking PDF generation dependencies...")
    print("=" * 50)
    
    # Check pdfkit
    try:
        import pdfkit
        print("✓ pdfkit is available")
        pdfkit_available = True
    except ImportError:
        print("✗ pdfkit is not available")
        pdfkit_available = False
    
    # Check wkhtmltopdf
    from shop_admin.utils import find_wkhtmltopdf_path
    wkhtmltopdf_path = find_wkhtmltopdf_path()
    
    if wkhtmltopdf_path:
        print(f"✓ wkhtmltopdf found at: {wkhtmltopdf_path}")
        wkhtmltopdf_available = True
    else:
        print("✗ wkhtmltopdf not found")
        wkhtmltopdf_available = False
    
    print("\nSummary:")
    print(f"  pdfkit: {'Available' if pdfkit_available else 'Not Available'}")
    print(f"  wkhtmltopdf: {'Available' if wkhtmltopdf_available else 'Not Available'}")
    
    if pdfkit_available and wkhtmltopdf_available:
        print("\n✓ PDF generation should work with pdfkit + wkhtmltopdf")
    else:
        print("\n✗ No suitable PDF generation method available")
        print("Please install pdfkit and wkhtmltopdf")
    
    return pdfkit_available and wkhtmltopdf_available

if __name__ == "__main__":
    print("PDF Generation Test Script")
    print("=" * 50)
    
    # Check dependencies first
    dependencies_ok = check_dependencies()
    print()
    
    if dependencies_ok:
        # Run PDF generation test
        success = test_pdf_generation()
        
        if success:
            print("\n🎉 PDF generation test completed successfully!")
        else:
            print("\n❌ PDF generation test failed!")
            sys.exit(1)
    else:
        print("\n❌ Required dependencies not available!")
        print("Please refer to PDF_SETUP.md for installation instructions.")
        sys.exit(1)
