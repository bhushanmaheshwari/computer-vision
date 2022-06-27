from flask import Flask, render_template,  request
from werkzeug.utils import secure_filename
import os
import sqlite3 as sql


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './static/uploads'


conn = sql.connect('database.db')
conn.execute('CREATE TABLE history_dev (name TEXT, path TEXT)')
conn.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/history')
def history():
    con = sql.connect("database.db")
    con.row_factory = sql.Row
   
    cur = con.cursor()
    cur.execute("select * from history_dev")
   
    rows = cur.fetchall(); 
    return render_template('history.html', rows=rows)


@app.route('/new')
def new():
    return render_template('new.html')


@app.route('/details', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        f = request.files['file']
        path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            secure_filename(f.filename)
        )
        f.save(path)

        try:
            with sql.connect("database.db") as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO history_dev(name, path) VALUES(?, ?)", (f.filename, path))
                con.commit()
                msg = "Record successfully added"
        except:
            con.rollback()
            msg = "error in insert operation"
        finally:
            con.close()
            return render_template('details.html', path=path)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
