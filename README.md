# Anand Mobiles Backend

A Django REST API backend for the Anand Mobiles e-commerce platform.

## Setup Instructions

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
5. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```
6. Run the development server:
   ```bash
   python manage.py runserver
   ```

## API Endpoints

- Admin API: `/api/admin/`
- User API: `/api/`
- API Authentication: `/api-auth/`
- API Documentation: `/docs/`

## Firebase Integration

This project uses Firebase for authentication and storage. The Firebase configuration is stored in `config_anand.json`.

## Frontend Integration

This backend is designed to work with a React frontend. The CORS settings are configured to allow requests from:
- http://localhost:3000
- http://127.0.0.1:3000

You can add more allowed origins in the `settings.py` file.

BUILD BY : Priyanshu Dayal @priyanshudayal1
