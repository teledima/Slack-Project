import firebase_admin
from firebase_admin import credentials

cred = credentials.Certificate('files/slash-commands-archive-99df74bbe787.json')
firebase_admin.initialize_app(cred)