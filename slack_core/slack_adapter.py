import json
from abc import abstractmethod, ABC

from pyee import EventEmitter
from flask.scaffold import Scaffold
from flask import request, jsonify, make_response


class SlackAdapter(EventEmitter, ABC):
    def __init__(self, router: Scaffold = None, rule=''):
        super().__init__()

        self.router = router
        if not isinstance(self.router, Scaffold):
            self.router = Scaffold(__name__)

        router.add_url_rule(rule, view_func=self.handler, methods=['POST'])

    @abstractmethod
    def handler(self):
        pass


class SlackEventAdapter(SlackAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handler(self):
        payload = request.json
        if payload.get('type') == 'url_verification':
            return jsonify(challenge=payload['challenge']), 200
        if payload.get('type') == 'event_callback':
            if payload['event']['type'] in self.event_names():
                self.emit(payload['event']['type'], payload)
            return make_response('', 200)


class SlackInteractionsAdapter(SlackAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handler(self):
        payload = json.loads(request.form['payload'])
        for i, event in enumerate(self.event_names()):
            assert len(event_path) == 2
            event_path = event.split('.')
            if payload.get('type') in ('shortcut', 'view_submission'):
                if event_path[0] == payload['type'] and event_path[1] == payload['view']['callback_id']:
                    response = dict()
                    self.emit(event, response)
                    return jsonify(response), 200
            elif payload.get('type') == 'block_actions':
                if event_path[0] == payload['type'] and event_path[1] == payload['actions'][0]['action_id']:
                    self.emit(event)
                    return make_response('', 200)
