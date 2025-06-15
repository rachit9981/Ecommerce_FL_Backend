#!/bin/bash

# PDF Generation Setup Script for Linux/macOS
# This script installs the necessary dependencies for PDF generation

echo "=== PDF Generation Setup for Ecommerce Backend ==="
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python and pip
if ! command_exists python3; then
    echo "❌ Python3 is not installed. Please install Python first."
    exit 1
fi

if ! command_exists pip3; then
    echo "❌ pip3 is not installed. Please install pip first."
    exit 1
fi

echo "✅ Python and pip are available"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install weasyprint reportlab

if [ $? -eq 0 ]; then
    echo "✅ Python dependencies installed successfully"
else
    echo "❌ Failed to install Python dependencies"
    exit 1
fi

# Install wkhtmltopdf based on the operating system
if command_exists apt-get; then
    # Ubuntu/Debian
    echo "🐧 Detected Debian/Ubuntu system"
    echo "📦 Installing wkhtmltopdf..."
    sudo apt-get update
    sudo apt-get install -y wkhtmltopdf xvfb
    
elif command_exists yum; then
    # CentOS/RHEL (older versions)
    echo "🐧 Detected CentOS/RHEL system"
    echo "📦 Installing wkhtmltopdf..."
    sudo yum install -y wkhtmltopdf
    
elif command_exists dnf; then
    # Fedora/CentOS/RHEL (newer versions)
    echo "🐧 Detected Fedora/CentOS/RHEL system"
    echo "📦 Installing wkhtmltopdf..."
    sudo dnf install -y wkhtmltopdf
    
elif command_exists brew; then
    # macOS with Homebrew
    echo "🍎 Detected macOS system"
    echo "📦 Installing wkhtmltopdf..."
    brew install wkhtmltopdf
    
else
    echo "⚠️ Could not detect package manager. Please install wkhtmltopdf manually:"
    echo "   Download from: https://wkhtmltopdf.org/downloads.html"
fi

# Verify installations
echo ""
echo "🔍 Verifying installations..."

if command_exists wkhtmltopdf; then
    echo "✅ wkhtmltopdf installed successfully"
    wkhtmltopdf --version
else
    echo "⚠️ wkhtmltopdf not found in PATH"
fi

# Test WeasyPrint
python3 -c "import weasyprint; print('✅ WeasyPrint imported successfully')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ WeasyPrint import failed"
fi

echo ""
echo "🎉 Setup completed!"
echo ""
echo "To test PDF generation, run:"
echo "   python3 test_pdf_generation.py"
echo ""
echo "For more information, see PDF_SETUP.md"
