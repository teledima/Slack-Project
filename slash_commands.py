import constants
import requests
import json
from flask import Flask, request
from znatoks import find_user_spreadsheet
from slackify import Slackify, async_task, reply_text
from slack.web.classes import blocks
from slack import WebClient

app = Flask(__name__)
slackify_app = Slackify(app=app)


def ephemeral_message(response_url, text):
    requests.post(response_url, data=json.dumps({'content_type': 'ephemeral', 'text': text}))


@slackify_app.command(name='get_info', methods=['POST'])
def get_info():
    user_url = request.form['text']
    response_url = request.form['response_url']
    if not user_url:
        return reply_text('Query is empty')
    get_info_background(user_url, response_url, request.form['channel_id'])
    return reply_text('Got it!')


@async_task
def get_info_background(user_url, response_url, channel_id):
    info = find_user_spreadsheet(user_url)
    if all(i is None for i in info):
        ephemeral_message(response_url, 'User does not found')
        return
    sections = []
    for row in info:
        if row:
            for key in row.keys():
                sections.append(
                    blocks.SectionBlock(text=blocks.TextObject(f'_*{key}*_: {row[key]}', 'mrkdwn')).to_dict())
        sections.append(blocks.DividerBlock().to_dict())
    WebClient(token=constants.SLACK_OAUTH_TOKEN).chat_postMessage(channel=channel_id, blocks=sections)
