import time

from flask import Flask, render_template, send_from_directory, request
import os, json, shutil, re
from datetime import datetime, timedelta
from PIL import Image



app = Flask(__name__)

@app.route('/<path:filename>')
def image_static(filename):
    return send_from_directory(image_folder_path, filename)


def load_settings_json(setting_json_path="../../.config/satdump/settings.json"):
    """
    Load satdump_cfg.json file and return the default output directory
    :return: file path
    """
    try:
        with open(setting_json_path, 'r') as f_in:

            # Read lines and filter out lines containing ' //'
            lines = [line.split(' //')[0] for line in f_in]

            # Concatenate lines into a single string
            json_content = ''.join(lines)

            # Replace true and false by "true", "false
            json_content.replace('true', '"true"')
            json_content.replace('false', '"false"')

            # Load JSON from the processed content
            setting_json  = json.loads(json_content)

            return setting_json["satdump_directories"]["default_output_directory"]["value"]

    except FileNotFoundError:
        print("Unable to find setting.json")
        return None


# set the image folder path
image_folder_path = load_settings_json() + '/'


def explore_directory(static_path, dir):
    """
    
    :param dir_path: 
    :return: list of images dict {'name': img, 'path':  img)}
    """
    images = []

    for img in os.listdir(os.path.join(static_path, dir)):

        if img != "Thumbnails":

            if os.path.join(static_path, dir, img).endswith(".png"):
                current = {'name': img, 'path': os.path.join(dir, img),}
                path_thumbnail = os.path.join(dir, "Thumbnails", "thumb_"+img)

                if os.path.exists(os.path.join(static_path, path_thumbnail)):
                    current['thumb'] = path_thumbnail

                images.append(current)

            elif os.path.isdir(os.path.join(static_path, dir, img)):
                i = explore_directory(static_path, os.path.join(dir, img))
                images = images + i


    return images

def get_images():
    """

    :return: return a list of dict for each passes
    """
    images = []
    for image_folder in os.listdir(image_folder_path):

        if os.path.isdir(os.path.join(image_folder_path, image_folder)):

            try:
                with open(os.path.join(image_folder_path, image_folder, "dataset.json")) as f_in:
                    passe_images = {'passe_info': json.load(f_in), 'pass_images': []}

            except FileNotFoundError:
                continue
            # change time to datatime obj
            passe_images['passe_info']['timestamp'] = datetime.fromtimestamp( passe_images['passe_info']['timestamp'])

            # Get the images for this passe
            passe_images["pass_images"] = explore_directory(image_folder_path, image_folder)

            images.append(passe_images)

    images = sorted(images, key=lambda x: x["passe_info"]["timestamp"], reverse=True)

    return images

def remove_old_passe(timelimitdays = 365 ):
    """
    if the passe is older than time limites in days delete the folder
    :param timelimitdays: Limit to setup in day
    :return: number of folder deleted
    """

    nb_dir_delete = 0
    now = datetime.utcnow()
    for image_folder in os.listdir(image_folder_path):
        
        if "dataset.json" in os.listdir(os.path.join(image_folder_path, image_folder)):
            with open(os.path.join(image_folder_path, image_folder, "dataset.json")) as f_in:
                passe_info = json.load(f_in)
                # change time to datatime obj
                time_passe = datetime.fromtimestamp(passe_info['timestamp'])

            if time_passe + timedelta(days=timelimitdays) < now:
                shutil.rmtree(os.path.join(image_folder_path, image_folder))
                nb_dir_delete = nb_dir_delete + 1
                
        elif datetime.fromtimestamp(os.path.getctime(os.path.join(image_folder_path, image_folder))) + timedelta(days=1) < now:
            print('Error occure, NO "dataset.json" in file: ', os.path.join(image_folder_path, image_folder), " and folser is older than 6h; Folder deletated")
            shutil.rmtree(os.path.join(image_folder_path, image_folder))
            nb_dir_delete = nb_dir_delete + 1
                

    return nb_dir_delete

def create_thumpnails(folder = image_folder_path):
    """
    Create thumbnail in each folder that has images
    :param folder to explore
    :return: number of thumnail created
    """
    list_folder = os.listdir(folder)
    nb_thumb = 0
    if "Thumbnails" not in list_folder:

        if folder != image_folder_path:
            os.makedirs(os.path.join(folder, "Thumbnails"), exist_ok=True)

        for file in list_folder:

            if os.path.join(folder, file).endswith(".png"):

                with Image.open(os.path.join(folder, file)) as img:

                    # Convert the image to 'RGB' if it's not in a compatible mode
                    if img.mode not in ('RGB', 'L'):
                        img = img.point(lambda i: i * (1.0 / 256)).convert('L')  # Rescale 16-bit to 8-bit
                    # Define the maximum size for the thumbnail (width, height)
                    size = 128, 128
                    # Create a thumbnail (this modifies the image in place)
                    img.thumbnail(size)

                    # Save the thumbnail to a new file

                    thumbnail_path = os.path.join(folder, "Thumbnails/", "thumb_" + file)
                    img.save(thumbnail_path)

                    nb_thumb = nb_thumb + 1


            elif os.path.isdir(os.path.join(folder, file)) and file != "Thumbnails":
                nb_thumb = nb_thumb + create_thumpnails(os.path.join(folder, file))

    return nb_thumb




@app.route('/')
def index():

    # warning the line bellow will delete the passes that are more than X days old.
    print(remove_old_passe(7), "directory remove")

    # Create Thumbnail
    print(create_thumpnails(), " thumbnails created")

    images = get_images()

    page = request.args.get('page', 1, type=int)
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    total_pages = int(round(len(images) / per_page, 0))

    images_on_page = images[start:end]


    return render_template('index.html', total_passes=len(images), images=images_on_page, total_pages=total_pages, page=page)


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)

