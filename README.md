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
├── render.yaml          # Render deployment configuration
├── Procfile             # Process file for web servers
├── runtime.txt          # Python runtime specification
└── README.md             # Project documentation
```

## Local Setup Instructions

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
   pnpm install
   ```

4. Create a `.env` file based on the `.env.example` template:
   ```
   cp .env.example .env
   ```

5. Configure your Supabase credentials in the `.env` file.

6. Run the application:
   ```
   uvicorn main:app --reload
   ```

## Deployment to Render

This project includes configuration files for deploying to Render.

### Prerequisites

1. Create a Render account at [render.com](https://render.com/)
2. Link your GitHub repository to Render

### Deployment Steps

1. From your Render dashboard, click on "New" and select "Blueprint" (or "Web Service" if not using the render.yaml blueprint)

2. If using Blueprint:
   - Connect your GitHub repository
   - Render will automatically detect the `render.yaml` file and configure the services

3. If using Web Service manually:
   - Select your GitHub repository
   - Use the following settings:
     - **Name**: `fastapi-supabase-app` (or your preferred name)
     - **Environment**: `Python`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

4. Configure environment variables in the Render dashboard:
   - Add all variables from your `.env` file, especially:
     - `SUPABASE_URL`
     - `SUPABASE_KEY`
     - `SUPABASE_SERVICE_KEY`

5. Click "Create Web Service"

### Updating Deployed Application

Render automatically deploys new versions when you push to your connected repository branch.

## Usage Guidelines

- Access the API documentation at `http://localhost:8000/docs` for local development or at your Render URL for the deployed version
- Use the authentication routes for user registration and login as defined in `app/auth/routes.py`

## License

This project is licensed under the MIT License.
