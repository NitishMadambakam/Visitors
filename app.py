from flask import Flask, redirect, url_for, request, render_template, flash, session, abort
import psycopg2
import os
from flask_session import Session
from key import secret_key, salt, salt2
from itsdangerous import URLSafeTimedSerializer
from stoken import token
from cmail import sendmail

app = Flask(__name__)
app.secret_key = secret_key
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Connect to PostgreSQL using psycopg2
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True  # Auto-commit after each query

@app.route('/')
def admin():
    return render_template('title.html')

@app.route('/adminlogin', methods=['GET', 'POST'])
def adminlogin():
    if session.get('user'):
        return redirect(url_for('admin'))
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        cursor = conn.cursor()
        cursor.execute('SELECT count(*) FROM admin WHERE username=%s AND password=%s', (name, password))
        count = cursor.fetchone()[0]
        cursor.close()
        if count == 1:
            session['admin'] = name
            return redirect(url_for('adminhome'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/adminhome')
def adminhome():
    if session.get('user'):
        return render_template('homepage.html')
    else:
        return redirect(url_for('adduser'))

@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        cursor = conn.cursor()
        cursor.execute('SELECT count(*) FROM admin WHERE username=%s', (username,))
        count = cursor.fetchone()[0]
        cursor.execute('SELECT count(*) FROM admin WHERE email=%s', (email,))
        count1 = cursor.fetchone()[0]
        cursor.close()
        if count == 1:
            flash('Username already in use')
        elif count1 == 1:
            flash('Email already in use')
        else:
            data = {'username': username, 'password': password, 'email': email}
            subject = 'Email Confirmation'
            body = f"Thanks for signing up\n\nFollow this link: {url_for('confirm', token=token(data, salt), _external=True)}"
            sendmail(to=email, subject=subject, body=body)
            flash('Confirmation link sent to your email')
            return redirect(url_for('adminlogin'))
    return render_template('registration.html')

@app.route('/confirm/<token>')
def confirm(token):
    try:
        serializer = URLSafeTimedSerializer(secret_key)
        data = serializer.loads(token, salt=salt, max_age=180)
    except Exception:
        return 'Link Expired. Register again.'
    else:
        cursor = conn.cursor()
        username = data['username']
        cursor.execute('SELECT count(*) FROM admin WHERE username=%s', (username,))
        count = cursor.fetchone()[0]
        if count == 1:
            flash('You are already registered!')
        else:
            cursor.execute('INSERT INTO admin(username, password, email) VALUES(%s, %s, %s)',
                           (data['username'], data['password'], data['email']))
            flash('Registration successful!')
        cursor.close()
        return redirect(url_for('adminlogin'))

@app.route('/forget', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email']
        cursor = conn.cursor()
        cursor.execute('SELECT count(*) FROM admin WHERE email=%s', (email,))
        count = cursor.fetchone()[0]
        if count == 1:
            confirm_link = url_for('reset', token=token(email, salt=salt2), _external=True)
            subject = 'Reset Password'
            body = f"Use this link to reset your password:\n\n{confirm_link}"
            sendmail(to=email, subject=subject, body=body)
            flash('Reset link sent to your email')
            cursor.close()
            return redirect(url_for('adminlogin'))
        else:
            flash('Invalid email address')
            cursor.close()
    return render_template('forgot.html')

@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset(token):
    try:
        serializer = URLSafeTimedSerializer(secret_key)
        email = serializer.loads(token, salt=salt2, max_age=180)
    except:
        abort(404, 'Link Expired')
    else:
        if request.method == 'POST':
            newpassword = request.form['npassword']
            confirmpassword = request.form['cpassword']
            if newpassword == confirmpassword:
                cursor = conn.cursor()
                cursor.execute('UPDATE admin SET password=%s WHERE email=%s', (newpassword, email))
                flash('Password reset successful')
                cursor.close()
                return redirect(url_for('adminlogin'))
            else:
                flash('Passwords do not match')
        return render_template('newpassword.html')

@app.route('/logout')
def logout():
    if session.get('user'):
        session.pop('user')
        flash('Successfully logged out')
    return redirect(url_for('adminlogin'))

@app.route('/adduser', methods=['GET', 'POST'])
def adduser():
    if request.method == 'POST':
        id1 = request.form['id1']
        fullname = request.form['name']
        mobile = request.form['mobile']
        room = request.form['room']
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users(user_id, name, room, phno) VALUES(%s, %s, %s, %s)', (id1, fullname, room, mobile))
        cursor.close()
        return redirect(url_for('visitor'))
    return render_template('Add-Users.html')

@app.route('/visitor', methods=['GET', 'POST'])
def visitor():
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    data = cursor.fetchall()
    cursor.execute('SELECT * FROM visitors')
    details = cursor.fetchall()
    cursor.close()
    if request.method == 'POST':
        id1 = request.form['id']
        name = request.form['name']
        mobile = request.form['mobile']
        cursor = conn.cursor()
        cursor.execute('INSERT INTO visitors(vid, vname, phno) VALUES(%s, %s, %s)', (id1, name, mobile))
        cursor.execute('SELECT * FROM visitors')
        details = cursor.fetchall()
        cursor.close()
    return render_template('VisitorRecord.html', data=data, details=details)

@app.route('/checkinvisitor/<id1>')
def checkinvisitor(id1):
    cursor = conn.cursor()
    cursor.execute('UPDATE visitors SET checkin=NOW() WHERE vid=%s', (id1,))
    cursor.close()
    return redirect(url_for('visitor'))

@app.route('/checkoutvisitor/<id1>')
def checkoutvisitor(id1):
    cursor = conn.cursor()
    cursor.execute('UPDATE visitors SET checkout=NOW() WHERE vid=%s', (id1,))
    cursor.close()
    return redirect(url_for('visitor'))

def create_tables():
    cursor = conn.cursor()  # ← ADD THIS LINE
    queries = [
        """
        CREATE TABLE IF NOT EXISTS admin (
            username VARCHAR(50) PRIMARY KEY,
            password VARCHAR(15),
            email VARCHAR(60)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY,
            name VARCHAR(50),
            room INT,
            phno BIGINT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS visitors (
            vid INT PRIMARY KEY,
            vname VARCHAR(50),
            checkin TIMESTAMP DEFAULT NULL,
            checkout TIMESTAMP DEFAULT NULL,
            phno VARCHAR(11),
            FOREIGN KEY (vid) REFERENCES users(user_id)
                ON UPDATE CASCADE ON DELETE CASCADE
        );
        """
    ]
    for q in queries:
        cursor.execute(q)
    cursor.close()  # ← GOOD PRACTICE TO CLOSE CURSOR


# Run this only once
create_tables()


if __name__ == '__main__':
    app.run(debug=True)