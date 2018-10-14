from flask import Flask, request, render_template, flash, redirect, url_for, session, logging
import os
from RegisterForm import RegisterForm
from FileForm import FileForm
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from passlib.hash import sha256_crypt
#from flask.ext.mysql import MySQL


UPLOAD_FOLDER = ''
ALLOWED_EXTENSIONS = set(['pdf'])

app = Flask('__name__')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
mysql  = MySQL()

#config mySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'theNurseNeedsFiles18#'
app.config['MYSQL_DB'] = 'FileUploader'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql.init_app(app)


@app.route('/')
def index():
    return render_template('index.html')

# User login
@app.route('/signin', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get Form Fields
        username = request.form['username']
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        if result > 0:
            # Get stored hash
            data = cur.fetchone()
            password = data['password']

            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid login'
                return render_template('signin.html', error=error)
            # Close connection
            cur.close()
        else:
            error = 'Username not found'
            return render_template('signin.html', error=error)

    return render_template('signin.html')

@app.route('/dashboard')
def dashboard():
    form = FileForm(request.form)
    if request.method == 'POST' and form.validate():
        fileName = form.fileName.data
        fileDescription = form.fileDescription.data
    return render_template('dashboard.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        cur = mysql.connection.cursor()

        cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)", (name, email, username, password))

        mysql.connection.commit()

        flash('You are now registered!', 'success')
        cur.close()
        #con.close()
        return render_template('signup.html', form = form)
    return render_template('signup.html', form = form)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('upload_file', filename=filename))
    return render_template('upload.html')

if __name__ == '__main__':
    app.secret_key = 'theNurseNeedsFiles18#'
    app.run(debug=True)
