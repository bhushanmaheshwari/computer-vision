import os
import sqlite3 as sql
from flask import Flask, render_template,  request
from werkzeug.utils import secure_filename
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials

import cv2
import matplotlib.pyplot as plt
import numpy as np


# sqlite
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './static/uploads'

conn = sql.connect('database.db')
conn.execute(
    'CREATE TABLE IF NOT EXISTS history_db_dev (name TEXT, path TEXT, description TEXT, tags TEXT, color TEXT, detectionPath TEXT)')
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

        image = cv2.imread(path)
        labelsPath = './static/yolo-coco/coco.names'

        LABELS = open(labelsPath).read().strip().split("\n")

        # initialize a list of colors to represent each possible class label
        COLORS = np.random.randint(0, 255, size=(len(LABELS), 3),
            dtype="uint8")

        # paths to the YOLO weights and model configuration
        weightsPath = './static/yolo-coco/yolov3.weights'
        configPath = './static/yolo-coco/yolov3.cfg'

        # load our YOLO object detector trained on COCO dataset (80 classes)
        net = cv2.dnn.readNetFromDarknet(configPath, weightsPath)

        (H, W) = image.shape[:2]

        # determine only the *output* layer names that we need from YOLO
        ln = net.getLayerNames()
        print(net.getUnconnectedOutLayers())
        ln = [ln[i - 1] for i in net.getUnconnectedOutLayers()]

        # construct a blob from the input image and then perform a forward
        # pass of the YOLO object detector, giving us our bounding boxes and
        # associated probabilities
        blob = cv2.dnn.blobFromImage(image, 1 / 255.0, (416, 416),
            swapRB=True, crop=False)
        net.setInput(blob)
        layerOutputs = net.forward(ln)

        # initialize our lists of detected bounding boxes, confidences, and
        # class IDs, respectively
        boxes = []
        confidences = []
        classIDs = []

        # loop over each of the layer outputs
        for output in layerOutputs:
            # loop over each of the detections
            for detection in output:
                # extract the class ID and confidence (i.e., probability) of
                # the current object detection
                scores = detection[5:]
                classID = np.argmax(scores)
                confidence = scores[classID]

                # filter out weak predictions by ensuring the detected
                # probability is greater than the minimum probability
                if confidence > 0.5:
                    # scale the bounding box coordinates back relative to the
                    # size of the image, keeping in mind that YOLO actually
                    # returns the center (x, y)-coordinates of the bounding
                    # box followed by the boxes' width and height
                    box = detection[0:4] * np.array([W, H, W, H])
                    (centerX, centerY, width, height) = box.astype("int")

                    # use the center (x, y)-coordinates to derive the top and
                    # and left corner of the bounding box
                    x = int(centerX - (width / 2))
                    y = int(centerY - (height / 2))

                    # update our list of bounding box coordinates, confidences,
                    # and class IDs
                    boxes.append([x, y, int(width), int(height)])
                    confidences.append(float(confidence))
                    classIDs.append(classID)

        # apply non-maxima suppression to suppress weak, overlapping bounding boxes
        idxs = cv2.dnn.NMSBoxes(boxes, confidences, 0.5,
            0.3)

        # ensure at least one detection exists
        if len(idxs) > 0:
            # loop over the indexes we are keeping
            for i in idxs.flatten():
                # extract the bounding box coordinates
                (x, y) = (boxes[i][0], boxes[i][1])
                (w, h) = (boxes[i][2], boxes[i][3])

                # draw a bounding box rectangle and label on the image
                color = [int(c) for c in COLORS[classIDs[i]]]
                cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
                text = "{}: {:.4f}".format(LABELS[classIDs[i]], confidences[i])
                cv2.putText(image, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, color, 2)

        # show the output image
        detectionPath = './static/detections/outputs/' + f.filename
        cv2.imwrite(detectionPath, image)
        try:
            with sql.connect("database.db") as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO history_db_dev(name, path, description, tags, color, detectionPath) VALUES(?, ?, ?, ?, ?,?)", (f.filename, path, description, tags, colors, detectionPath))
                print("Record successfully added")
                con.commit()
        except:
            print("error in insert operation")
            con.rollback()
        finally:
            con.close()
            return render_template('details.html', filename=f.filename, path=path, description=description, tags=image_analysis.tags, color=colors, detectionPath=detectionPath)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
