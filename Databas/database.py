from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'hemligt :)'
DATABASE = 'database.db'

# Funktionen som skapas och används av create_function som finns i sqllite
def _get_num_students(course_id):
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Kollar hur många studenter som finns på en specifik kurs
    cursor.execute('''
        SELECT num_students FROM courses
        WHERE course_id = ?
    ''', (course_id,))

    num_students = cursor.fetchone()[0]
    connection.close()

    return num_students

def create_tables():
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Skapar tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY,
            name TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            course_id INTEGER PRIMARY KEY,
            name TEXT,
            num_students INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            course_id INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (course_id) REFERENCES courses(course_id)
        )
    ''')

    # Trigger som ökar num students för courses vid insert på registration
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_course_count
        AFTER INSERT ON registrations
        FOR EACH ROW
        BEGIN
            UPDATE courses
            SET num_students = num_students + 1
            WHERE course_id = NEW.course_id;
        END;
    ''')

    connection.commit()
    connection.close()

def add_test_data():
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Fyller våra tables med värden
    cursor.execute("INSERT OR IGNORE INTO students (student_id, name) VALUES (1, 'Pontus Östryd')")
    cursor.execute("INSERT OR IGNORE INTO students (student_id, name) VALUES (2, 'Rasmus Petersson')")
    cursor.execute("INSERT OR IGNORE INTO students (student_id, name) VALUES (3, 'Anders Andersson')")
    cursor.execute("INSERT OR IGNORE INTO students (student_id, name) VALUES (4, 'Anna Andersson')")

    cursor.execute("INSERT OR IGNORE INTO courses (course_id, name) VALUES (1, 'Matte')")
    cursor.execute("INSERT OR IGNORE INTO courses (course_id, name) VALUES (2, 'Engelska')")
    cursor.execute("INSERT OR IGNORE INTO courses (course_id, name) VALUES (3, 'Historia')")
    cursor.execute("INSERT OR IGNORE INTO courses (course_id, name) VALUES (4, 'Svenska')")

    connection.commit()
    connection.close()

def get_all_courses():
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Hämtar alla kurser
    cursor.execute('SELECT name, course_id FROM courses')
    courses = cursor.fetchall()

    all_courses = []
    for course in courses:
        course_name = course[0]
        course_id = course[1]

        # Använder funktion för att hämta antalet studenter
        num_students = _get_num_students(course_id)
        all_courses.append((course_name, course_id, num_students))

    connection.close()

    return all_courses

def get_available_courses(student_id):
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Hämtar de kurser som studenten inte är registrerad på
    cursor.execute('''
        SELECT c.name, c.course_id
        FROM courses AS c
        LEFT JOIN registrations AS r
        ON c.course_id = r.course_id AND r.student_id = ?
        WHERE r.course_id IS NULL
    ''', (student_id,))

    available_courses = cursor.fetchall()
    connection.close()

    return available_courses

def get_registered_courses(student_id):
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Hämtar de kurser som studenten är registrerad på
    cursor.execute('''
        SELECT c.name, c.course_id
        FROM courses AS c
        INNER JOIN registrations AS r ON c.course_id = r.course_id
        WHERE r.student_id = ?
    ''', (student_id,))

    registered_courses = cursor.fetchall()
    connection.close()

    return registered_courses

def get_student_name(student_id):
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Hämtar studentens namn
    cursor.execute('SELECT name FROM students WHERE student_id = ?', (student_id,))
    result = cursor.fetchone()

    connection.close()

    if result is not None:
        return result[0]
    else:
        return None


def get_registered_students_by_course():
    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Hämtar och grupperar med GROUP_CONCAT alla kurser, samt vilka studenter som är registrerade på dessa
    cursor.execute('''
        SELECT c.course_id, c.name, GROUP_CONCAT(s.name) AS registered_students
        FROM courses AS c
        LEFT JOIN registrations AS r ON c.course_id = r.course_id
        LEFT JOIN students AS s ON r.student_id = s.student_id
        GROUP BY c.course_id, c.name
    ''')

    registered_students = cursor.fetchall()
    connection.close()

    return registered_students

@app.route('/')
def index():
    # Kollar om inloggad, annars till login
    if 'student_id' in session:
        # Kör allt och kör render_template (flask)
        student_id = session['student_id']
        student_name = get_student_name(student_id)
        all_courses = get_all_courses()
        available_courses = get_available_courses(student_id)
        registered_courses = get_registered_courses(student_id)
        registered_students = get_registered_students_by_course()

        return render_template('index.html', student_name=student_name, all_courses=all_courses,
                           available_courses=available_courses, registered_courses=registered_courses,
                           registered_students=registered_students)
    else:
        return redirect(url_for('login'))

@app.route('/register', methods=['POST'])
def register_courses():
    # Registrerar student på de kurser som är ikryssade
    if 'student_id' in session:
        student_id = session['student_id']
        selected_courses = request.form.getlist('courses[]')

        if selected_courses:
            connection = sqlite3.connect(DATABASE)
            cursor = connection.cursor()

            # Lägger till kurserna i studentens registrerade kurser
            for course_id in selected_courses:
                cursor.execute("INSERT INTO registrations (student_id, course_id) VALUES (?, ?)", (student_id, course_id))

            connection.commit()
            connection.close()
    else:
        return redirect(url_for('login'))

    return redirect(url_for('index'))

@app.route('/remove', methods=['POST'])
def remove_course():
    # Tar bort studenten från kurser
    if 'student_id' not in session:
        return redirect(url_for('login'))

    student_id = session['student_id']
    course_id = request.form.get('course_id')

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Ta bort registrerad kurs från studenten
    cursor.execute("DELETE FROM registrations WHERE student_id = ? AND course_id = ?", (student_id, course_id))

    # Inbyggd funktionskapare för sqllite som skapar en funktion, som tar in 1 parameter 
    connection.create_function("get_num_students", 1, _get_num_students)

    # Minska registrerade studenter mha vår user defined function
    cursor.execute("UPDATE courses SET num_students = get_num_students(course_id) - 1 WHERE course_id = ?", (course_id,))

    connection.commit()
    connection.close()

    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Logga in på kursregistreringen
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        if not student_id:
            return render_template('login.html', error='Skriv in ditt student ID')

        student_name = get_student_name(student_id)
        if not student_name:
            return render_template('login.html', error='Felaktigt ID')

        session['student_id'] = student_id
        return redirect(url_for('index'))

    return render_template('login.html', error=None)

@app.route('/logout', methods=['GET'])
def reset_session():
    # Reset session och tillbaka till inlogg
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Kör allt!
    create_tables()
    add_test_data()
    app.run(debug=True)