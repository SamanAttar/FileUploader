from flask import Flask, request,requests, render_template, flash, redirect, url_for, session, logging, Response, stream_with_context, json
import os, random
from flask_mysqldb import MySQL

#import forms
from RegisterForm import RegisterForm
from FileForm import FileForm
from ContactForm import ContactForm

#security imports
from werkzeug.utils import secure_filename
from passlib.hash import sha256_crypt

#AWS imports
from config import S3_BUCKET, S3_LOCATION, S3_KEY, S3_SECRET
from helpers import s3
import boto
import boto.s3
from boto.s3.key import Key
import boto3
import botocore

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

@app.route('/', methods=['GET','POST'])
def index():
    form = FileForm(request.form)
    if request.method == 'POST' and form.validate():
        firstName = form.firstName.data
        lastName = form.lastName.data
        print(firstName)
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

# TODO: create a mapping between fileId and another
# IDEA: count how many files a user has in the DB, and store that as a secondary id
    # to reference the files
@app.route('/displayFile/<string:id>')
def displayFile(id):
    cur = mysql.connection.cursor()
    query = cur.execute("SELECT userId, fileURL FROM files WHERE s3id = %s", [id])
    query = cur.fetchone()

    try:
        if query['userId'] == session['userId']:
            response = download(query['fileURL'])
            return(response)
        else:
            error = 'No such file'
            return render_template('index.html', error=error)
    except Exception as e:
        error = "No such file"
        return render_template('index.html', error=error)

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
            s3id = str(random.randint(1,80000000000000000000000))

            cur = mysql.connection.cursor()
            query = cur.execute("SELECT s3id FROM files")
            query = cur.fetchall()
            cur.close()

            #Check to see the ungodly coincidence that this ID is already taken
            # Maybe this isn't even worth doing O(n) complexity for a small chance
            for row in query:
                if row['s3id'] is s3id:
                    s3id = str(random.randint(1,80000000000000000000000))
            #fileValue stores the URL
            fileURL = str(upload_file_to_s3(file, filename, fileContentType, S3_BUCKET, s3id, acl="public-read"))
            #flash (fileValue, 'danger')
            userId = session["userId"]

            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO files(userId, fileName, fileDescription, fileURL, s3id) VALUES(%s, %s, %s, %s, %s)", (userId, fileName, fileDescription, fileURL, s3id))
            mysql.connection.commit()
            cur.close()

            flash('File Saved!', 'success')
    return(redirect(url_for('dashboard')))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    currentUserId = session['userId']
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT name, email, username FROM users WHERE id = %s", [currentUserId])
    result = cur.fetchone()
    cur.close()

    with app.open_resource('./static/json/particleJSON.json') as f:
        json_data = json.load(f)
    return render_template('profile.html', result=result, json_data=json_data)

@app.route('/view_files', methods=['GET', 'POST'])
def view_files():
    # TODO either encrypt and create a new session token every few minutes
    currentUserId = session['userId']
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT admin FROM users WHERE id = %s", [currentUserId])
    result = cur.fetchone()
    cur.close()
    #Check to see if the user is an admin
    # if true get all files in the DB
    if '1' in str(result):
        cur = mysql.connection.cursor()
        # Get all the files
        result = cur.execute("SELECT fileName, s3id, fileDescription FROM files")
        rows = cur.fetchall()
        cur.close()
        
    #get the files of a specific user
    else:
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT fileName, s3id, fileDescription FROM files WHERE userId = %s", [currentUserId])
        rows = cur.fetchall()
        cur.close()
    return rows

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_file_to_s3(file, fileName, fileContentType, bucket_name, s3id, acl="public-read"):
    # Docs: http://boto3.readthedocs.io/en/latest/guide/s3.html
    try:
        s3.upload_fileobj(
            file,
            bucket_name,
            s3id,
            ExtraArgs={
                "ACL": acl,
                "ContentType" : fileContentType
            }
        )
    except Exception as e:
        print("Something Happened: ", e)
        return e
    return "{}{}".format(S3_LOCATION, s3id)

# TODO: Optimize Download Time
def download(url):
    req = requests.get(url, stream=True)
    return Response(stream_with_context(req.iter_content()), content_type=req.headers['content-type'])

if __name__ == '__main__':
    app.secret_key = 'theNurseNeedsFiles18#'
    app.run(debug=True)
