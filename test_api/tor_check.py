from flask import Blueprint, jsonify
from torpy.http.requests import TorRequests

tor_check_blueprint = Blueprint(name='tor_check', import_name=__name__)


@tor_check_blueprint.route('/test_api/tor_check/<int:count_circuit>')
def hello(count_circuit: int):
    res = dict()
    with TorRequests() as tor_requests:
        for i in range(count_circuit):
            with tor_requests.get_session() as sess:
                res[f"circuit_{i}"] = sess.get('https://check.torproject.org/api/ip').json()
    return jsonify(res)
