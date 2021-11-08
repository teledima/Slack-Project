from flask import Flask
from views_slack.view_endpoint import views_endpoint_blueprint
from events_slack.event_endpoint import event_endpoint_blueprint
from authorization import auth_blueprint
from test_api.smiles_check import smiles_check_blueprint
from znatok_helper_api import znatok_helper_blueprint


app = Flask(__name__)
app.register_blueprint(views_endpoint_blueprint)
app.register_blueprint(event_endpoint_blueprint)
app.register_blueprint(auth_blueprint)
app.register_blueprint(smiles_check_blueprint)
app.register_blueprint(znatok_helper_blueprint)


@app.route('/')
def hello():
    return "Hello, Slack App!"
