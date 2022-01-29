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
        pass
