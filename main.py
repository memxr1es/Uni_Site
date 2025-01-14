from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory
import sqlite3
from datetime import datetime
import os
from uuid import uuid4
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Путь для загрузки изображений
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Ограничение на размер файла (например, 16MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Создание и подключение к базе данных SQLite
def init_db():
    with sqlite3.connect('events.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL,
                            email TEXT NOT NULL,
                            password TEXT NOT NULL,
                            profile_image TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            description TEXT NOT NULL,
                            date TEXT NOT NULL,
                            genre TEXT NOT NULL,
                            image TEXT NOT NULL)''')
        conn.commit()

# Главная страница
@app.route('/')
def index():
    if 'id' in session:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['id'],)).fetchone()
        conn.close()
    elif 'id' not in session:
        return redirect(url_for('login'))

    # Получаем текущего пользователя
    with sqlite3.connect('events.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['id'],))
        user = cursor.fetchone()

    genre_filter = request.args.get('genre') 

    # Получаем список афиш
    with sqlite3.connect('events.db') as conn:
        cursor = conn.cursor()
        if genre_filter:
            cursor.execute("SELECT * FROM events WHERE genre = ? ORDER BY date ASC", (genre_filter,))
        else:
            cursor.execute("SELECT * FROM events ORDER BY date ASC")
        events = cursor.fetchall()

    genres = ["Музыка", "Кино", "Театр", "Выставки", "Спортивные события"]
    return render_template_string(TEMPLATES['home'], events=events, genres=genres, genre_filter=genre_filter, user = user)

def get_db_connection():
    conn = sqlite3.connect('events.db')
    conn.row_factory = sqlite3.Row  # Это позволяет обращаться к строкам как к словарям
    return conn

# Страница регистрации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user:
            return 'Пользователь с таким именем уже существует', 400

        # Сохраняем нового пользователя в базе данных
        conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
        conn.commit()
        conn.close()
        
        # Сохраняем имя пользователя в сессии
        session['username'] = username
        
        return redirect('/')  # Перенаправляем на главную страницу

    return render_template_string(TEMPLATES['register'])

# Страница авторизации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Проверка, есть ли такой пользователь с этим паролем
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['username'] = username 
            session['id'] = user['id'] # Сохраняем имя пользователя в сессии
            return render_template_string(TEMPLATES['home'], user = user) # Перенаправляем на главную страницу
        else:
            return 'Неверные данные', 400

    return render_template_string(TEMPLATES['login'])

# Функция для проверки расширения файла
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Страница профиля
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # Получаем текущего пользователя
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['id'],)).fetchone()
    conn.close()

    if request.method == 'POST':
        # Получаем новые данные
        username = request.form['username']
        email = request.form['email']
        profile_image = request.files['profile_image']
        image_filename = None
        
        # Обработка изображения, если оно было загружено

        if profile_image and allowed_file(profile_image.filename):  # Проверь расширение файла
            ext = os.path.splitext(profile_image.filename)[1]
            image_filename = secure_filename(f"photo_{uuid4().hex}{ext}")
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            profile_image.save(image_path)
        
        else:
            image_filename = user['profile_image']
        
        # Открываем соединение с базой данных
        with sqlite3.connect('events.db') as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET username = ?, email = ?, profile_image = ? WHERE id = ?',
                        (username, email, image_filename, user['id']))
            conn.commit()
        
        # Перенаправляем на страницу профиля с обновленными данными
        return redirect(url_for('index'))
    
    return render_template_string(TEMPLATES['profile'], user = user)

# Добавление новой афиши
@app.route('/add_event', methods=['GET', 'POST'])
def add_event():
    if 'id' not in session:
        return redirect(url_for('register'))

    genres = ["Музыка", "Кино", "Театр", "Выставки", "Спортивные события"]

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        date = request.form['date']
        genre = request.form['genre']
        
        # Загрузка изображения
        image = request.files['image']
        image_filename = None
        if image and allowed_file(image.filename):
            ext = os.path.splitext(image.filename)[1]
            image_filename = secure_filename(f"photo_{uuid4().hex}{ext}")
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)

        with sqlite3.connect('events.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO events (name, description, date, genre, image) VALUES (?, ?, ?, ?, ?)",
                           (name, description, date, genre, image_filename))
            conn.commit()

        return redirect(url_for('index'))

    return render_template_string(TEMPLATES['add_event'], genres=genres)

# Редактирование афиши
@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'id' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect('events.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()

    genres = ["Музыка", "Кино", "Театр", "Выставки", "Спортивные события"]

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        date = request.form['date']
        genre = request.form['genre']
        
        # Загрузка нового изображения
        image = request.files['image']
        image_filename = event[5]
        if image and allowed_file(image.filename):
            image_filename = secure_filename(f"{uuid4().hex}{os.path.splitext(image.filename)[1]}")
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        else:
            image_filename = event[5]

        with sqlite3.connect('events.db') as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE events SET name = ?, description = ?, date = ?, genre = ?, image = ? WHERE id = ?",
                           (name, description, date, genre, image_filename, event_id))
            conn.commit()

        return redirect(url_for('index'))

    return render_template_string(TEMPLATES['edit_event'], event=event, genres=genres)

# Удаление афиши
@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    if 'id' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect('events.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()

    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.pop('id', None)  # Удаляем ID пользователя из сессии
    return redirect(url_for('index'))

# Шаблоны в виде строк HTML
TEMPLATES = {
    'home': '''
    <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    background: linear-gradient(135deg, #333 0%, #764ba2 100%);
                    margin: 0;
                    padding: 0;
                    color: #333;
                }
                .header {
                    background-color: #333;
                    color: white;
                    padding: 40px 20px;
                    text-align: center;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }
                .header h1 {
                    font-size: 36px;
                    margin: 0;
                    font-weight: bold;
                }
                .button {
                    background-color: #4CAF50;
                    color: white;
                    padding: 12px 20px;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    text-decoration: none;
                    font-size: 16px;
                    transition: all 0.3s ease;
                    margin: 10px 0;
                }
                .button:hover {
                    transform: scale(1.1); /* Увеличение кнопки при наведении */
                    background-color: #007bff; /* Изменение цвета фона */
                }
                .filters {
                    text-align: center;
                    margin: 20px 0;
                }
                .filters form {
                    display: inline-block;
                    background-color: #fff;
                    padding: 15px;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }
                select {
                    padding: 8px;
                    font-size: 16px;
                    border-radius: 6px;
                    border: 1px solid #ddd;
                    width: 200px;
                    margin-top: 10px;
                    cursor: pointer;
                    transition: border-color 0.3s;
                }
                select:focus {
                    border-color: #4CAF50;
                    outline: none;
                }
                .section {
                    margin: 30px auto;
                    max-width: 1200px;
                    padding: 20px;
                }
                .event-card {
                    background-color: #fff;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    margin-bottom: 20px;
                    transition: transform 0.3s;
                }
                .event-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
                }
                .profile-image {
                    width: 50px;
                    height: 50px;
                    border-radius: 50px;
                }
                .event-card h3 {
                    margin-top: 0;
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                }
                .event-card p {
                    font-size: 16px;
                    color: #666;
                    margin: 10px 0;
                }
                .event-card img {
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                    margin: 10px 0;
                }
                .event-card .button {
                    display: inline-block;
                    margin-right: 10px;
                    padding: 10px 15px;
                    font-size: 16px;
                    background-color: #007bff;
                    border-radius: 5px;
                    text-decoration: none;
                    transition: background-color 0.3s;
                }
                .event-card .button:hover {
                    background-color: #0056b3;
                }
                .event-card .button.delete {
                    background-color: #dc3545;
                }
                .event-card .button.delete:hover {
                    background-color: #c82333;
                }
                .hoho {
                    margin-bottom: 20px;
                    border-radius: 10px;
                }
                hr {
                    border: 0;
                    border-top: 1px solid #eee;
                    margin: 20px 0;
                }
                footer {
                    text-align: center;
                    padding: 20px;
                    background-color: #333;
                    color: white;
                    margin-top: 50px;
                    font-size: 14px;
                }
                .user-info {
                    display: flex;
                    justify-content: center;
                    margin-top: 20px;
                    margin-bottom: 40px;
                }
                .user-info a {
                    margin-left: 20px;
                    margin-top: 15px;
                    font-size: 16px;
                    color: inherit; /* blue colors for links too */
                    text-decoration: inherit; /* no underline */
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Добро пожаловать в Event Calendar</h1>
                <div>
                    {% if session.get('username') %}
                        {% if user[4] %}
                        <div class = "user-info">
                            <img src="{{ url_for('uploaded_file', filename=user[4]) }}" alt="Изображение профиля" class="profile-image">
                            <a href="{{ url_for('profile') }}" >{{ session['username'] }}</a>
                        </div>
                        {% else %}
                            <p>Нет изображения профиля</p>
                        {% endif %}
                        <a href="{{ url_for('logout') }}" class="button logout-button">Logout</a>
                        <a href="{{ url_for('add_event') }}" class="button">Add Event</a>
                        <a href="{{ url_for('profile') }}" class="button">Редактировать профиль</a>
                    {% else %}
                        <p>Пожалуйста, войдите в систему.</p>
                        <a href="{{ url_for('login') }}" class="button logout-button">Log in</a>
                    {% endif %}
                </div>
            </div>


            <div class="section">
                <div class="header hoho">
                    <h2 >Upcoming Events</h2>
                    <form method="GET">
                        <label for="genre">Filter by Genre:</label>
                        <select name="genre" id="genre" onchange="this.form.submit()">
                            <option value="">All</option>
                            {% for genre in genres %}
                                <option value="{{ genre }}" {% if genre == genre_filter %} selected {% endif %}>{{ genre }}</option>
                            {% endfor %}
                        </select>
                    </form>
                </div>
                {% if events %}
                    <div class="event-cards">
                        {% for event in events %}
                            <div class="event-card">
                                <h3>{{ event[1] }}</h3>
                                <p>{{ event[2] }}</p>
                                <p><strong>Date:</strong> {{ event[3] }}</p>
                                <p><strong>Genre:</strong> {{ event[4] }}</p>
                                <img src="{{ url_for('uploaded_file', filename=event[5]) }}" alt="Event Image">
                                <br>
                                <a href="{{ url_for('edit_event', event_id=event[0]) }}" class="button">Edit</a>
                                <a href="{{ url_for('delete_event', event_id=event[0]) }}" class="button delete">Delete</a>
                                <hr>
                            </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <p>No events found. Try selecting a different genre or check back later.</p>
                {% endif %}
            </div>
        </body>
    </html>
    ''',

    'login': '''
 <html>
    <head>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background-color: #f5f5f5;
                margin: 0;
                padding: 0;
                color: #333;
            }
            .header {
                background-color: #333;
                color: white;
                padding: 40px 20px;
                text-align: center;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            .header h1 {
                font-size: 36px;
                margin: 0;
                font-weight: bold;
            }
            .form-container {
                width: 100%;
                max-width: 400px;
                margin: 50px auto;
                padding: 20px;
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            input[type="text"], input[type="password"] {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            input[type="text"]:focus, input[type="password"]:focus {
                border-color: #4CAF50;
                outline: none;
            }
            .button {
                background-color: #4CAF50;
                color: white;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                text-decoration: none;
                font-size: 16px;
                transition: background-color 0.3s;
                width: 100%;
            }
            .button:hover {
                background-color: #45a049;
            }
            .link {
                display: block;
                text-align: center;
                margin-top: 20px;
            }
            footer {
                text-align: center;
                padding: 20px;
                background-color: #333;
                color: white;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Login</h1>
        </div>
        <div class="form-container">
            <form method="POST">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required>
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
                <button type="submit" class="button">Login</button>
            </form>
            <div class="link">
                <a href="{{ url_for('register') }}">Don't have an account? Register</a>
            </div>
        </div>

        <footer>
            <p>&copy; 2025 Event Calendar. All rights reserved.</p>
        </footer>
    </body>
</html>
    ''',

    'register': '''
<html>
    <head>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background-color: #f5f5f5;
                margin: 0;
                padding: 0;
                color: #333;
            }
            .header {
                background-color: #333;
                color: white;
                padding: 40px 20px;
                text-align: center;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            .header h1 {
                font-size: 36px;
                margin: 0;
                font-weight: bold;
            }
            .form-container {
                width: 100%;
                max-width: 400px;
                margin: 50px auto;
                padding: 20px;
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            input[type="text"], input[type="password"], input[type="email"] {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            input[type="text"]:focus, input[type="password"]:focus, input[type="email"]:focus {
                border-color: #4CAF50;
                outline: none;
            }
            .button {
                background-color: #4CAF50;
                color: white;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                text-decoration: none;
                font-size: 16px;
                transition: background-color 0.3s;
                width: 100%;
            }
            .button:hover {
                background-color: #45a049;
            }
            .link {
                display: block;
                text-align: center;
                margin-top: 20px;
            }
            footer {
                text-align: center;
                padding: 20px;
                background-color: #333;
                color: white;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Register</h1>
        </div>
        <div class="form-container">
            <form method="POST">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required>
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required>
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
                <button type="submit" class="button">Register</button>
            </form>
            <div class="link">
                <a href="{{ url_for('login') }}">Already have an account? Login</a>
            </div>
        </div>
        <footer>
            <p>&copy; 2025 Event Calendar. All rights reserved.</p>
        </footer>
    </body>
</html>
    ''',

    'profile': '''
        <html>
        <head>
            <title>Профиль</title>
            <style>
            .container {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f4f4f4;
                border-radius: 10px;
            }

            h2 {
                text-align: center;
            }

            .form-group {
                margin-bottom: 15px;
            }

            input[type="text"], input[type="email"], input[type="file"] {
                width: 100%;
                padding: 10px;
                margin-top: 5px;
                border-radius: 5px;
                border: 1px solid #ccc;
            }

            button {
                padding: 10px 20px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                width: 100%;
            }

            button:hover {
                background-color: #0056b3;
            }

            .profile-image {
                width: 100px;
                height: 100px;
                border-radius: 50%;
                object-fit: cover;
                margin-bottom: 10px;
            }

            .user-info {
                text-align: center;
            }

            .user-info p {
                margin: 10px 0;
            }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Редактирование профиля</h2>
                <form action="/profile" method="POST" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="username">Имя:</label>
                        <input type="text" id="username" name="username" value="{{ user['username'] }}" required>
                    </div>
                    <div class="form-group">
                        <label for="email">Email:</label>
                        <input type="email" id="email" name="email" value="{{ user['email'] }}" required>
                    </div>
                    <div class="form-group">
                        <label for="profile_image">Изображение профиля:</label>
                        <input type="file" id="profile_image" name="profile_image">
                    </div>
                    <button type="submit" class="btn">Сохранить изменения</button>
                </form>
            </div>
        </body>
    </html>
    ''',

    'add_event': '''
<html>
    <head>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background-color: #f5f5f5;
                margin: 0;
                padding: 0;
                color: #333;
            }
            .header {
                background-color: #333;
                color: white;
                padding: 40px 20px;
                text-align: center;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            .header h1 {
                font-size: 36px;
                margin: 0;
                font-weight: bold;
            }
            .form-container {
                width: 100%;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            input[type="text"], input[type="file"], input[type="date"], textarea {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            input[type="text"]:focus, input[type="file"]:focus, input[type="date"]:focus, textarea:focus {
                border-color: #4CAF50;
                outline: none;
            }
            .button {
                background-color: #4CAF50;
                color: white;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                text-decoration: none;
                font-size: 16px;
                transition: background-color 0.3s;
                width: 100%;
            }
            .button:hover {
                background-color: #45a049;
            }
            footer {
                text-align: center;
                padding: 20px;
                background-color: #333;
                color: white;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Add New Event</h1>
        </div>
        <div class="form-container">
            <form method="POST" action="/add_event" enctype="multipart/form-data">
                <label for="title">Event Title</label>
                <input type="text" id="name" name="name" required>
                <label for="description">Event Description</label>
                <textarea id="description" name="description" rows="4" required></textarea>
                <label for="date">Event Date</label>
                <input type="date" id="date" name="date" required>
                <label for="genre">Genre</label>
                <input type="text" id="genre" name="genre" required>
                <label for="image">Upload Image</label>
                <input type="file" id="image" name="image" accept="image/*" required>
                <button type="submit" class="button">Add Event</button>
            </form>
        </div>
        <footer>
            <p>&copy; 2025 Event Calendar. All rights reserved.</p>
        </footer>
    </body>
</html>
    ''',

    'edit_event': '''
    <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; background: #f3f4f7; display: flex; justify-content: center; align-items: center; height: 100vh; }
                .card { background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 0 15px rgba(0, 0, 0, 0.1); width: 400px; }
                .button { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; width: 100%; }
                .button:hover { background-color: #45a049; }
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Edit Event</h2>
                <form method="POST" enctype="multipart/form-data">
                    Event Name: <input type="text" name="name" value="{{ event[1] }}" required><br><br>
                    Description: <textarea name="description" required>{{ event[2] }}</textarea><br><br>
                    Date: <input type="date" name="date" value="{{ event[3] }}" required><br><br>
                    Genre:
                    <select name="genre">
                        {% for genre in genres %}
                            <option value="{{ genre }}" {% if genre == event[4] %}selected{% endif %}>{{ genre }}</option>
                        {% endfor %}
                    </select><br><br>
                    Image: <input type="file" name="image"><br><br>
                    <button type="submit" class="button">Update Event</button>
                </form>
            </div>

            <footer>
                <p>&copy; 2025 Event Calendar. All rights reserved.</p>
            </footer>

        </body>
    </html>
    '''
}

if __name__ == '__main__':
    init_db()
    app.run(debug=True)