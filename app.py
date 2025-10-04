from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
import os
import json
from datetime import datetime
import processing2 as processing
from dotenv import load_dotenv, find_dotenv

"""
Load environment variables from a .env file. We first look for a .env next to this file,
and fall back to searching upward in the directory tree. This mirrors the logic in
`processing.py` so the app behaves the same regardless of how it's started.
"""
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(dotenv_path):
    dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

app = Flask(__name__)

# Configure CORS origins via env, default to allowing all
cors_origins = [o.strip() for o in os.getenv('CORS_ORIGINS', '*').split(',')] if os.getenv('CORS_ORIGINS') else '*'
CORS(app, resources={r"/api/*": {"origins": cors_origins}, r"/upload": {"origins": cors_origins}})

# Secret key from env
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-change-me')

# Configuration
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
max_mb = int(os.getenv('MAX_CONTENT_MB', '16'))
app.config['MAX_CONTENT_LENGTH'] = max_mb * 1024 * 1024  # in bytes

# Create uploads directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Sample user data (in production, use a proper database)
users = {
    'admin@example.com': {
        'name': 'Admin User',
        'email': 'admin@example.com',
        'password': 'admin123',
        'role': 'teacher'
    },
    'student@example.com': {
        'name': 'Student User',
        'email': 'student@example.com',
        'password': 'student123',
        'role': 'student'
    }
}


@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/login')
def login():
    """Login page"""
    return render_template('login.html')

@app.route('/signup')
def signup():
    """Signup page"""
    return render_template('signup.html')

@app.route('/courses')
def courses_page():
    """Courses page"""
    return render_template('courses.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for login"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if email in users and users[email]['password'] == password:
        session['user'] = {
            'name': users[email]['name'],
            'email': email,
            'role': users[email]['role']
        }
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': session['user']
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Invalid credentials'
        }), 401

@app.route('/api/signup', methods=['POST'])
def api_signup():
    """API endpoint for signup"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    
    if email in users:
        return jsonify({
            'success': False,
            'message': 'User already exists'
        }), 400
    
    # Add new user
    users[email] = {
        'name': f"{first_name} {last_name}",
        'email': email,
        'password': password,
        'role': 'student'
    }
    
    session['user'] = {
        'name': users[email]['name'],
        'email': email,
        'role': 'student'
    }
    
    return jsonify({
        'success': True,
        'message': 'Account created successfully',
        'user': session['user']
    })

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """API endpoint for logout"""
    session.pop('user', None)
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })

@app.route('/api/user')
def api_user():
    """Get current user info"""
    if 'user' in session:
        return jsonify({
            'success': True,
            'user': session['user']
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Not logged in'
        }), 401


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Handle course material upload"""
    if 'user' not in session:
        return jsonify({
            'success': False,
            'message': 'Authentication required'
        }), 401
    
    if session['user']['role'] != 'teacher':
        return jsonify({
            'success': False,
            'message': 'Teacher access required'
        }), 403
    
    subject_name = request.form.get('subjectName')
    file = request.files.get('pdfUpload')
    
    if not subject_name or not file:
        return jsonify({
            'success': False,
            'message': 'Subject name and file are required'
        }), 400
    
    if file.filename == '':
        return jsonify({
            'success': False,
            'message': 'No file selected'
        }), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        filename = f"{subject_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Analyze the uploaded PDF as an attendance sheet
        try:
            results = processing.process_pdf(filepath)
            if isinstance(results, dict) and 'error' in results:
                return jsonify({
                    'success': False,
                    'error': results.get('error')
                }), 400
            return jsonify({
                'success': True,
                'data': results
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Failed to analyze PDF: {str(e)}'
            }), 500
    else:
        return jsonify({
            'success': False,
            'message': 'Only PDF files are allowed'
        }), 400


# New endpoint: process attendance image via processing.process_image
@app.route('/api/process', methods=['POST'])
def api_process():
    """Process an uploaded attendance image and return structured results."""
    # Expecting multipart/form-data with a file field named 'file'
    file = request.files.get('file')
    if not file:
        return jsonify({
            'success': False,
            'message': "No file part in the request; expected field name 'file'"
        }), 400

    if file.filename == '':
        return jsonify({
            'success': False,
            'message': 'No file selected'
        }), 400

    # Save the uploaded file
    name, ext = os.path.splitext(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = f"{name}_{timestamp}{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
    file.save(filepath)

    # Delegate processing to the processing module
    try:
        results = processing.process_image(filepath)
        # processing.process_image returns a dict; include success flag for consistency
        if isinstance(results, dict) and 'error' in results:
            return jsonify({
                'success': False,
                'error': results.get('error')
            }), 400
        return jsonify({
            'success': True,
            'data': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to process image: {str(e)}'
        }), 500


# Backward-compatibility: support the old FastAPI-style endpoint path
@app.route('/upload', methods=['POST'])
def upload_compat():
    """Compatibility endpoint mirroring main.py's /upload."""
    return api_process()


if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', '0') in ('1', 'true', 'True')
    app.run(debug=debug, host=host, port=port)
