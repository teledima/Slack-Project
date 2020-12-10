from slack_core.functions_slack import check_empty, is_admin, reply, ephemeral_message
from slack_sdk.web import WebClient
from slack_core.tasks import async_task
from slack_sdk.models import blocks
from flask import Blueprint, request
from slack_core import constants
import znatoks


get_info_blueprint = Blueprint('get_info', __name__)


@get_info_blueprint.route('/get_info', methods=['POST'])
def get_info():
    req = request.form
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
    if not is_admin(client, req['user_id']):
        return reply("You don't have permission")
    check_empty(req)
    get_info_background(request.form)
    return reply('Got it!')


@async_task
def get_info_background(req):
    info = znatoks.find_user_spreadsheet(req['text'])
    if all(i is None for i in info):
        ephemeral_message(req['response_url'], 'User is not found')
        return
    sections = []
    for row in info:
        if row is not None:
            for key in row.keys():
                sections.append(
                    blocks.SectionBlock(text=blocks.TextObject(f'_*{key}*_: {row[key]}', 'mrkdwn')).to_dict())
            sections.append(blocks.DividerBlock().to_dict())
    ephemeral_message(req['response_url'], blocks=sections)