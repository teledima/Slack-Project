from flask import Flask, render_template
from views_slack import views_endpoint_blueprint
from events_slack import event_endpoint_blueprint
from authorization import auth_blueprint
from channels_checker.worker import channels_checker_blueprint

app = Flask(__name__)
blueprints = [
    views_endpoint_blueprint,
    event_endpoint_blueprint,
    auth_blueprint,
    channels_checker_blueprint
]
for bp in blueprints:
    app.register_blueprint(bp)


@app.route('/')
def hello():
    return "Hello, Slack App!"


@app.route('/latex-page', methods=["GET"])
def latex_page():
    return render_template('latex_page/latex_page.html')
