from flask import Blueprint, jsonify
from firebase_admin import firestore

smiles_check_blueprint = Blueprint(name='smiles_check', import_name=__name__)
smiles_collection = firestore.client().collection('smiles')


@smiles_check_blueprint.route('/test_api/smiles_check/<string:emoji>')
def smile_check(emoji: str):
    doc = smiles_collection.document(emoji).get()
    if doc.exists:
        return jsonify(success=True, expert_name=doc.to_dict()['expert_name'])
    else:
        return jsonify(success=False, code=200)
