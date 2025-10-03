# A. P. Shah Institute of Technology - Flask Web Application

A modern educational platform built with Flask backend and responsive frontend.

## Features

- **User Authentication**: Login and signup with session management
- **Course Management**: View available courses and enroll
- **Teacher Upload**: Teachers can upload course materials (PDF files)
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Dark/Light Theme**: Toggle between themes with persistent preferences
- **Modern UI**: Clean, professional interface with animations

## Project Structure

```
StyleRefresh/
├── app.py                 # Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   └── courses.html
├── static/               # Static assets
│   ├── style.css
│   ├── auth.css
│   ├── courses.css
│   ├── script.js
│   └── auth.js
└── uploads/             # Uploaded files (created automatically)
```

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Installation

1. **Clone or download the project**
   ```bash
   cd "D:\Galactic Debuggers\StyleRefresh"
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Open your browser**
   Navigate to: `http://localhost:5000`

## Usage

### Default Users

The application comes with pre-configured users for testing:

**Teacher Account:**
- Email: `admin@example.com`
- Password: `admin123`

**Student Account:**
- Email: `student@example.com`
- Password: `student123`

### Features Overview

1. **Home Page** (`/`): Landing page with hero section
2. **Login** (`/login`): User authentication
3. **Signup** (`/signup`): New user registration
4. **Courses** (`/courses`): Browse and enroll in courses
   - Teachers can upload PDF course materials
   - Students can enroll in available courses

### API Endpoints

- `POST /api/login` - User login
- `POST /api/signup` - User registration
- `POST /api/logout` - User logout
- `GET /api/user` - Get current user info
- `GET /api/courses` - Get all courses
- `POST /api/upload` - Upload course material (teachers only)
- `POST /api/enroll` - Enroll in course

## Development

### Running in Development Mode

The application runs in debug mode by default, which provides:
- Automatic reloading on code changes
- Detailed error messages
- Debug toolbar

### Customization

- **Styling**: Modify CSS files in the `static/` directory
- **Backend Logic**: Update `app.py` for server-side functionality
- **Templates**: Edit HTML files in the `templates/` directory

### Adding New Features

1. **New Routes**: Add to `app.py`
2. **New Templates**: Create in `templates/` directory
3. **New Static Files**: Add to `static/` directory
4. **Database**: Replace in-memory storage with a proper database (SQLite, PostgreSQL, etc.)

## Production Deployment

For production deployment:

1. **Change the secret key** in `app.py`
2. **Set debug=False** in `app.py`
3. **Use a production WSGI server** (Gunicorn, uWSGI)
4. **Set up a reverse proxy** (Nginx, Apache)
5. **Use a production database**
6. **Set up proper file storage** (AWS S3, Google Cloud Storage)

## Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## License

This project is for educational purposes.
