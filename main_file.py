from flask import Flask
from slash_commands.wonderful_answer import wonderful_answer_blueprint
from slash_commands.get_info import get_info_blueprint
from views_slack.view_endpoint import views_endpoint_blueprint
from events_slack.event_endpoint import event_endpoint_blueprint
from slack_core.limiter import limiter


app = Flask(__name__)
limiter.init_app(app)
app.register_blueprint(wonderful_answer_blueprint)
app.register_blueprint(get_info_blueprint)
app.register_blueprint(views_endpoint_blueprint)
app.register_blueprint(event_endpoint_blueprint)


@app.route('/')
def hello():
    return "Hello, Slack App!"
