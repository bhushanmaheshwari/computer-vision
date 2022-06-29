import os
import sqlite3 as sql
from flask import Flask, render_template,  request
from werkzeug.utils import secure_filename
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials

# sqlite
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './static/uploads'

conn = sql.connect('database.db')
conn.execute(
    'CREATE TABLE IF NOT EXISTS history_db_dev (name TEXT, path TEXT, description TEXT, tags TEXT, color TEXT)')
conn.close()

# azure computer vision api
key = '76a73a58680a4d45ad7f9428c572fa27'
endpoint = 'https://cogser-one.cognitiveservices.azure.com/'

credentials = CognitiveServicesCredentials(key)
client = ComputerVisionClient(
    endpoint=endpoint,
    credentials=credentials
)


@app.route('/')
def index():
    con = sql.connect("database.db")
    con.row_factory = sql.Row
    cur = con.cursor()
    cur.execute("select * from history_db_dev")
    rows = cur.fetchall()
    return render_template('index.html',  rows=rows)


@app.route('/details', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        f = request.files['file']
        path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            secure_filename(f.filename)
        )
        f.save(path)

        with open(path, "rb") as image_stream:
            image_analysis = client.analyze_image_in_stream(
                image=image_stream,
                visual_features=[
                    VisualFeatureTypes.image_type,  # Could use simple str "ImageType"
                    VisualFeatureTypes.faces,      # Could use simple str "Faces"
                    VisualFeatureTypes.categories,  # Could use simple str "Categories"
                    VisualFeatureTypes.color,      # Could use simple str "Color"
                    VisualFeatureTypes.tags,       # Could use simple str "Tags"
                    VisualFeatureTypes.description  # Could use simple str "Description"
                ]
            )

        description = ''
        description = image_analysis.description.captions[0].text
        tags = ''
        for tag in image_analysis.tags:
            tags += ("{}\t-\t{:0.2f}%".format(tag.name, tag.confidence * 100)) + ' | '

        colors = ''
        for color in image_analysis.color.dominant_colors:
            colors += color + ', '

        try:
            with sql.connect("database.db") as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO history_db_dev(name, path, description, tags, color) VALUES(?, ?, ?, ?, ?)", (f.filename, path, description, tags, colors))
                print("Record successfully added")
                con.commit()
        except:
            print("error in insert operation")
            con.rollback()
        finally:
            con.close()
            return render_template('details.html', filename=f.filename, path=path, description=description, tags=image_analysis.tags, color=colors)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
