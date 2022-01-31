from firebase_admin import credentials, initialize_app, firestore


cred = credentials.Certificate('files/slash-commands-archive-99df74bbe787.json')
initialize_app(cred)
firestore_client = firestore.client()
authed_users_collection = firestore.client().collection('authed_users')
smiles_collection = firestore_client.collection('smiles')
settings_collection = firestore_client.collection('users_settings')
