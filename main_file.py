from flask import Flask
from views_slack.view_endpoint import views_endpoint_blueprint
from events_slack.event_endpoint import event_endpoint_blueprint
from authorization import auth_blueprint
from test_api.smiles_check import smiles_check_blueprint
from znatok_helper_api import znatok_helper_blueprint
from channels_checker.worker import channels_checker_blueprint

app = Flask(__name__)
blueprints = [
    views_endpoint_blueprint,
    event_endpoint_blueprint,
    auth_blueprint,
    smiles_check_blueprint,
    znatok_helper_blueprint,
    channels_checker_blueprint
]
for bp in blueprints:
    app.register_blueprint(bp)


@app.route('/')
def hello():
    return "Hello, Slack App!"
