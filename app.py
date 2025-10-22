from flask import Flask, redirect, url_for, request, render_template, flash, session, abort
import mysql.connector
from flask_session import Session
from itsdangerous import URLSafeTimedSerializer
from key import secret_key, salt, salt2
from stoken import token
from cmail import sendmail

app = Flask(__name__)
app.secret_key = secret_key
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# MySQL connection
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="admin",
    database="visitors"
)

# ---------------- HOME ---------------- #
@app.route('/')
def admin():
    return render_template('title.html')


# ---------------- ADMIN LOGIN ---------------- #
@app.route('/adminlogin', methods=['GET', 'POST'])
def adminlogin():
    if session.get('admin'):
        return redirect(url_for('adminhome'))
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        cursor = mydb.cursor(buffered=True)
        cursor.execute('SELECT COUNT(*) FROM admin WHERE username=%s AND password=%s', [name, password])
        count = cursor.fetchone()[0]
        cursor.close()
        if count == 1:
            session['admin'] = name
            return redirect(url_for('adminhome'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')


# ---------------- ADMIN HOME ---------------- #
@app.route('/adminhome')
def adminhome():
    if session.get('admin'):
        return render_template('homepage.html')
    return redirect(url_for('adminlogin'))


# ---------------- REGISTRATION ---------------- #
@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        cursor = mydb.cursor(buffered=True)
        cursor.execute('SELECT COUNT(*) FROM admin WHERE username=%s', [username])
        count_user = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM admin WHERE email=%s', [email])
        count_email = cursor.fetchone()[0]
        cursor.close()

        if count_user:
            flash('Username already in use')
        elif count_email:
            flash('Email already in use')
        else:
            data = {'username': username, 'password': password, 'email': email}
            confirm_link = url_for('confirm', token=token(data, salt), _external=True)
            body = f"Thanks for signing up!\n\nFollow this link to confirm your email: {confirm_link}"
            sendmail(to=email, subject='Email Confirmation', body=body)
            flash('Confirmation link sent to email')

    return render_template('registration.html')


# ---------------- CONFIRMATION ---------------- #
@app.route('/confirm/<token>')
def confirm(token):
    try:
        serializer = URLSafeTimedSerializer(secret_key)
        data = serializer.loads(token, salt=salt, max_age=180)
    except:
        return 'Link expired. Please register again.'

    cursor = mydb.cursor(buffered=True)
    username = data['username']
    cursor.execute('SELECT COUNT(*) FROM admin WHERE username=%s', [username])
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO admin (username, password, email) VALUES (%s, %s, %s)',
                       [data['username'], data['password'], data['email']])
        mydb.commit()
        flash('Registration successful! Please login.')
    else:
        flash('You are already registered!')
    cursor.close()
    return redirect(url_for('adminlogin'))


# ---------------- FORGOT PASSWORD ---------------- #
@app.route('/forget', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email']
        cursor = mydb.cursor(buffered=True)
        cursor.execute('SELECT COUNT(*) FROM admin WHERE email=%s', [email])
        count = cursor.fetchone()[0]
        cursor.close()

        if count:
            reset_link = url_for('reset', token=token(email, salt2), _external=True)
            body = f"Use this link to reset your password:\n{reset_link}"
            sendmail(to=email, subject='Password Reset', body=body)
            flash('Reset link sent to your email')
            return redirect(url_for('adminlogin'))
        else:
            flash('Invalid email ID')

    return render_template('forgot.html')


# ---------------- RESET PASSWORD ---------------- #
@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset(token):
    try:
        serializer = URLSafeTimedSerializer(secret_key)
        email = serializer.loads(token, salt=salt2, max_age=180)
    except:
        abort(404, 'Link Expired')

    if request.method == 'POST':
        newpassword = request.form['npassword']
        confirmpassword = request.form['cpassword']
        if newpassword == confirmpassword:
            cursor = mydb.cursor(buffered=True)
            cursor.execute('UPDATE admin SET password=%s WHERE email=%s', [newpassword, email])
            mydb.commit()
            cursor.close()
            flash('Password reset successful')
            return redirect(url_for('adminlogin'))
        else:
            flash('Passwords do not match')

    return render_template('newpassword.html')


# ---------------- LOGOUT ---------------- #
@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('Successfully logged out')
    return redirect(url_for('adminlogin'))


# ---------------- ADD USER ---------------- #
@app.route('/adduser', methods=['GET', 'POST'])
def adduser():
    if request.method == 'POST':
        fullname = request.form['name']
        mobile = request.form['mobile']
        room = request.form['room']

        cursor = mydb.cursor(buffered=True)
        cursor.execute('SELECT COUNT(*) FROM users WHERE fullname=%s AND room=%s', [fullname, room])
        if cursor.fetchone()[0]:
            flash(f"User {fullname} in room {room} already exists")
            cursor.close()
            return redirect(url_for('adduser'))

        cursor.execute('INSERT INTO users (fullname, room, mobile) VALUES (%s, %s, %s)',
                       [fullname, room, mobile])
        mydb.commit()
        cursor.close()
        flash(f"User {fullname} added successfully")
        return redirect(url_for('visitor'))

    return render_template('Add-Users.html')


# ---------------- VISITOR RECORD ---------------- #
@app.route('/visitor', methods=['GET', 'POST'])
def visitor():
    if request.method == 'POST':
        user_id = request.form['id']
        name = request.form['name']
        mobile = request.form['mobile']

        cursor = mydb.cursor(buffered=True)
        cursor.execute('INSERT INTO visitors (uid, vname, phno) VALUES (%s, %s, %s)', 
                       [user_id, name, mobile])
        mydb.commit()
        cursor.close()
        flash(f"Visitor {name} added successfully")
        return redirect(url_for('visitor'))

    # Fetch data AFTER insert/redirect
    cursor = mydb.cursor(buffered=True)
    cursor.execute('SELECT uid, fullname FROM users')
    users = cursor.fetchall()
    cursor.execute('SELECT * FROM visitors ORDER BY vid DESC')
    visitors = cursor.fetchall()
    cursor.close()

    return render_template('VisitorRecord.html', data=users, details=visitors)



# ---------------- CHECK-IN & CHECK-OUT ---------------- #
@app.route('/checkinvisitor/<int:vid>')
def checkinvisitor(vid):
    cursor = mydb.cursor(buffered=True)
    cursor.execute('UPDATE visitors SET checkin=CURRENT_TIMESTAMP() WHERE vid=%s', [vid])
    mydb.commit()
    cursor.close()
    return redirect(url_for('visitor'))

@app.route('/checkoutvisitor/<int:vid>')
def checkoutvisitor(vid):
    cursor = mydb.cursor(buffered=True)
    cursor.execute('UPDATE visitors SET checkout=CURRENT_TIMESTAMP() WHERE vid=%s', [vid])
    mydb.commit()
    cursor.close()
    return redirect(url_for('visitor'))


# ---------------- RUN APP ---------------- #
if __name__ == '__main__':
    app.run(debug=True)
