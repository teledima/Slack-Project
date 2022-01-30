from flask import Blueprint

from slack_core import SlackEventAdapter
from .reaction_added import reaction_added
from .app_home_opened import app_home_opened

event_endpoint_blueprint = Blueprint('event_endpoint', __name__)
slack_event_adapter = SlackEventAdapter(router=event_endpoint_blueprint, rule='/event_endpoint')

slack_event_adapter.on('reaction_added', reaction_added)
slack_event_adapter.on('app_home_opened', app_home_opened)
