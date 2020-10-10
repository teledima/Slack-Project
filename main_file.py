from flask import Flask
from slash_commands.wonderful_answer import wonderful_answer_blueprint
from slash_commands.get_info import get_info_blueprint
from views_slack import view_endpoint


app = Flask(__name__)
app.register_blueprint(wonderful_answer_blueprint)
app.register_blueprint(get_info_blueprint)
app.register_blueprint(view_endpoint)


@app.route('/')
def hello():
    return "Hello, Slack App!"
