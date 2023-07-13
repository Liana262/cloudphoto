import argparse
import configparser
import errno
import os
from pathlib import Path
import uuid
import hashlib
import boto3

CONFIG_FILE_DIRECTORY = fr'{os.path.expanduser("~")}\.config\cloudphoto\cloudphotorc\config.ini'


def read_cred_from_config():
    config = configparser.ConfigParser()
    config.read(f"{CONFIG_FILE_DIRECTORY}")
    nf_list = []
    if 'DEFAULT' not in config:
        print("Error config file")
        exit(1)
    config_data = config["DEFAULT"]
    aws_access_key_id = config_data.get("aws_access_key_id", fallback=None)
    if aws_access_key_id is None:
        nf_list.append("aws_access_key_id")

    aws_secret_access_key = config_data.get("aws_secret_access_key", fallback=None)
    if aws_secret_access_key is None:
        nf_list.append("aws_secret_access_key")

    BUCKET = config_data.get("bucket", fallback=None)
    if BUCKET is None:
        nf_list.append("bucket")

    region_name = config_data.get("region", fallback=None)
    if region_name is None:
        nf_list.append("region")

    endpoint_url = config_data.get("endpoint_url", fallback=None)
    if endpoint_url is None:
        nf_list.append("endpoint_url")

    if len(nf_list) > 0:
        print(f"Not found next parameters:\n{nf_list}\nPlease run init")
        exit(1)
    return aws_access_key_id, aws_secret_access_key, BUCKET, region_name, endpoint_url


ALBUM_PREFIX = 'albums'
PHOTO_PREFIX = 'photos'

parser = argparse.ArgumentParser(description='Action')
parser.add_argument('action', type=str)
parser.add_argument('ALBUM', type=str, nargs='*')
parser.add_argument('--album', type=str, nargs='+')
parser.add_argument('--path', type=str)

args = parser.parse_args()
action = args.action
aws_access_key_id, aws_secret_access_key, BUCKET, region_name, endpoint_url = read_cred_from_config()


def pre_init():
    ycls = boto3.session.Session(aws_access_key_id=aws_access_key_id,
                                 aws_secret_access_key=aws_secret_access_key,
                                 region_name=region_name)
    yclr = ycls.resource(service_name='s3', endpoint_url=endpoint_url)
    yclb = yclr.Bucket(BUCKET)
    return ycls, yclr, yclb


if action != "init":
    admin_session, admin_resource, admin_pub_bucket = pre_init()


def get_list(need_return):
    album_dict = {}

    for dir in admin_pub_bucket.objects.filter(Prefix=ALBUM_PREFIX):
        album_from_cloud_name = str(dir.get()['Body'].read().decode('utf-8'))
        album_dict[album_from_cloud_name] = dir.key.split("/")[1]

    my_keys = list(album_dict.keys())
    my_keys.sort()
    sorted_dict = {i: album_dict[i] for i in my_keys}

    if need_return:
        return sorted_dict

    if len(album_dict) == 0:
        print('Photo albums not found')
        exit(1)

    for a in sorted_dict:
        print(a)

    exit(0)


def get_uuid_from_name(name):
    return 0


def create_new_album(name):
    album_new_uuid = uuid.uuid4()
    album_object = admin_resource.Object(BUCKET, f'{ALBUM_PREFIX}/{album_new_uuid}')
    album_object.put(Body=str.encode(name))
    return album_new_uuid


def upload():
    album_name = args.album
    album_name_str = ""
    l = len(album_name)
    for i in range(l):
        if i == l - 1:
            album_name_str += album_name[i]
        else:
            album_name_str += album_name[i] + " "

    photo_dir_path = args.path
    album_dict = get_list(True)
    if album_dict.get(album_name_str) is None:
        album_uuid = create_new_album(album_name_str)
    else:
        album_uuid = album_dict[album_name_str]

    if str(photo_dir_path).strip() == 'None':
        photo_dir_path = r'.'

    else:
        photo_dir_path = rf'{photo_dir_path}'

    files_path = Path(photo_dir_path)

    if not files_path.is_dir():
        print(f"Warning: No such directory <{photo_dir_path}>")
        exit(1)

    files = files_path.glob('*.jpg')
    files_list = []
    for f in files:
        files_list.append(f)

    files = files_path.glob('*.jpeg')
    for f in files:
        files_list.append(f)

    if len(files_list) == 0:
        print(f"Warning: Photos not found in directory <{photo_dir_path}>")
        exit(1)

    for file in files_list:
        try:
            photo_uuid = hashlib.sha256(file.name.encode()).hexdigest()
            photo_key = f'{PHOTO_PREFIX}/{album_uuid}/{photo_uuid}.jpg'
            photo_object = admin_resource.Object(BUCKET, photo_key)
            photo_object.upload_file(file)
        except any:
            print(f'Warning: Photo not sent {file.name}')
            continue
    exit(0)


def delete():
    album_name = args.ALBUM
    if str("".join(album_name)) == '':
        print('The following arguments are required: ALBUM')
        exit(1)

    album_name_str = ""
    l = len(album_name)
    for i in range(l):
        if i == l - 1:
            album_name_str += album_name[i]
        else:
            album_name_str += album_name[i] + " "

    album_dicts = get_list(True)
    album_uuid = album_dicts.get(album_name_str)

    if str(album_uuid) == 'None':
        print(f'Warning: Photo album not found <{album_name_str}>')
        exit(1)

    for obj in admin_pub_bucket.objects.all():
        if album_uuid in obj.key:
            obj.delete()
    exit(0)


def get_album_photo(album_uuid):
    album_list = []
    for dir in admin_pub_bucket.objects.filter(Prefix=PHOTO_PREFIX):
        if album_uuid in dir.key:
            album_list.append(f"""<img src="{endpoint_url}/{BUCKET}/{dir.key}" data-title="{dir.key}">""")
    return album_list


def generate_error_html():
    html_object = admin_pub_bucket.Object('error.html')
    error_html_content = """<html>
    <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <title>Фотоархив</title>
    </head>
<body>
    <h1>Ошибка</h1>
    <p>Ошибка при доступе к фотоархиву. Вернитесь на <a href="index.html">главную страницу</a> фотоархива.</p>
</body>
</html>"""
    html_object.put(Body=error_html_content, ContentType='text/html')


def generate_album_html():
    cloud_album_dict = get_list(True)
    index = 0
    for album in cloud_album_dict.values():
        index += 1
        album_photo = get_album_photo(album)
        html_object = admin_pub_bucket.Object(f'album{index}.html')
        album_html_content = f"""
                <!doctype html>
        <html>
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/galleria/1.6.1/themes/classic/galleria.classic.min.css" />
                <style>
                    .galleria{{ width: 960px; height: 540px; background: #000 }}
                </style>
                <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/galleria/1.6.1/galleria.min.js"></script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/galleria/1.6.1/themes/classic/galleria.classic.min.js"></script>
            </head>
            <body>
                <div class="galleria">
                {"".join(album_photo)}
                </div>
                <p>Вернуться на <a href="index.html">главную страницу</a> фотоархива</p>
                <script>
                    (function() {{
    Galleria.run('.galleria');
    }}());
                </script>
            </body>
        </html>
"""
        html_object.put(Body=album_html_content, ContentType='text/html')


def generate_index_html():
    html_object = admin_pub_bucket.Object('index.html')
    cloud_album_dict = get_list(True)
    album_items = []
    index = 0
    for album in cloud_album_dict.keys():
        index += 1
        album_items.append(f'<li><a href="album{index}.html">{album}</a></li>')
    html_content = f"""<!doctype html>
<html>
    <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <title>Фотоархив</title>
    </head>
<body>
    <h1>Фотоархив</h1>
    <ul>
    {"".join(album_items)}
    </ul>
</body"""
    html_object.put(Body=html_content, ContentType='text/html')
    generate_album_html()
    generate_error_html()


def mksite():
    bucket_website = admin_pub_bucket.Website()
    index_document = {'Suffix': 'index.html'}
    error_document = {'Key': 'error.html'}
    bucket_website.put(WebsiteConfiguration={'ErrorDocument': error_document, 'IndexDocument': index_document})
    generate_index_html()
    print(f"https://{admin_pub_bucket.name}.website.yandexcloud.net")


def init():
    print("Enter aws_access_key_id:")
    aws_access_key_id = input()
    print("Enter aws_secret_access_key:")
    aws_secret_access_key = input()
    print("Enter bucket:")
    bucket = input()

    user_session = boto3.session.Session(aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key)
    user_resource = user_session.resource(service_name='s3', endpoint_url=endpoint_url)
    user_pub_bucket = user_resource.Bucket(bucket)

    user_pub_bucket.create()
    user_pub_bucket.Acl().put(ACL='public-read')

    filename = f"{CONFIG_FILE_DIRECTORY}"
    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

    with open(filename, "w") as f:
        f.write("[DEFAULT]\n")
        f.write(f"bucket = {bucket}\n")
        f.write(f"aws_access_key_id = {aws_access_key_id}\n")
        f.write(f"aws_secret_access_key = {aws_secret_access_key}\n")
        f.write("region = ru-central1\n")
        f.write("endpoint_url = https://storage.yandexcloud.net")
        f.close()
    exit(0)


if action == "list":
    get_list(False)
elif action == "upload":
    upload()
elif action == "delete":
    delete()
elif action == "mksite":
    mksite()
elif action == "init":
    init()
