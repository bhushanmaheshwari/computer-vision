from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history')
def previous():
    return render_template('history.html')

@app.route('/new')
def new():
    return render_template('new.html')


if __name__ == '__main__': 
    app.run(host='0.0.0.0', port=5000)
