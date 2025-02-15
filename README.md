# fastapi-supabase-app/fastapi-supabase-app/README.md

# FastAPI Supabase App

This project is a FastAPI application integrated with Supabase for backend functionalities, focusing on authentication and database management.

## Project Structure

```
fastapi-supabase-app
├── app
│   ├── main.py          # Entry point of the FastAPI application
│   ├── auth             # Authentication module
│   │   ├── __init__.py  # Initializes the authentication module
│   │   ├── routes.py    # Authentication routes for user registration and login
│   │   └── schemas.py   # Pydantic models for authentication requests and responses
│   ├── db               # Database module
│   │   ├── __init__.py  # Initializes the database module
│   │   └── models.py    # SQLAlchemy models for the application
│   └── core             # Core configuration module
│       ├── __init__.py  # Initializes the core module
│       └── config.py    # Configuration settings for the application
├── requirements.txt      # Project dependencies
└── README.md             # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd fastapi-supabase-app
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure your Supabase credentials in `app/core/config.py`.

5. Run the application:
   ```
   uvicorn app.main:app --reload
   ```

## Usage Guidelines

- Access the API documentation at `http://localhost:8000/docs` after running the application.
- Use the authentication routes for user registration and login as defined in `app/auth/routes.py`.

## License

This project is licensed under the MIT License.