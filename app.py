from flask import Flask, request, render_template, flash, redirect, url_for, session, logging
import os
from RegisterForm import RegisterForm
from FileForm import FileForm
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from passlib.hash import sha256_crypt
from config import S3_BUCKET, S3_LOCATION, S3_KEY, S3_SECRET
from helpers import s3
import boto
import boto.s3
from boto.s3.key import Key
import boto3


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

@app.route('/test')
def test():
    return render_template('test.html')

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
            userId = data['id']

            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username
                session['userId'] = userId

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

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    form = FileForm(request.form)
    if request.method == 'POST' and form.validate():
        fileName = form.fileName.data
        fileDescription = form.fileDescription.data
    rows = view_files()
    return render_template('dashboard.html', form=form, rows=rows)

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

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']

        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            form = FileForm(request.form)

            fileName = form.fileName.data
            fileDescription = form.fileDescription.data
            fileContentType = file.content_type

            #the actual filename from the uploaded file
            filename = secure_filename(file.filename)

            #fileValue stores the URL
            fileURL = str(upload_file_to_s3(file, filename, fileContentType, S3_BUCKET, acl="public-read"))
            #flash (fileValue, 'danger')
            userId = session["userId"]

            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO files(userId, fileName, fileDescription, fileURL) VALUES(%s, %s, %s, %s)", (userId, fileName, fileDescription, fileURL))
            mysql.connection.commit()
            cur.close()

            flash('File Saved!', 'success')
    return(redirect(url_for('dashboard')))

@app.route('/view_files', methods=['GET', 'POST'])
def view_files():
    # TODO: Should not store userID in the session
    # either encrypt and create a new session token every few minutes 
    currentUserId = session['userId']
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT admin FROM users WHERE id = %s", [currentUserId])
    result = cur.fetchone()
    cur.close()
    #Check to see if the user is an admin
    # if true
    if '1' in str(result):
        cur = mysql.connection.cursor()
        # Get all the files
        result = cur.execute("SELECT * FROM files")
        rows = cur.fetchall()
        cur.close()
    else:
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM files WHERE userId = %s", [currentUserId])
        rows = cur.fetchall()
        cur.close()
    return rows

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_file_to_s3(file, fileName, fileContentType, bucket_name, acl="public-read"):
    # Docs: http://boto3.readthedocs.io/en/latest/guide/s3.html
    try:
        s3.upload_fileobj(
            file,
            bucket_name,
            fileName,
            ExtraArgs={
                "ACL": acl,
                "ContentType" : fileContentType
            }
        )
    except Exception as e:
        print("Something Happened: ", e)
        return e
    return "{}{}".format(S3_LOCATION, file.filename)


if __name__ == '__main__':
    app.secret_key = 'theNurseNeedsFiles18#'
    app.run(debug=True)
