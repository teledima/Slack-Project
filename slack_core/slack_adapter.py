from abc import abstractmethod, ABC

from pyee import EventEmitter
from flask.scaffold import Scaffold


class SlackAdapter(EventEmitter, ABC):
    def __init__(self, router: Scaffold, rule=''):
        super().__init__()

        self.router = router
        if not self.router:
            self.router = Scaffold(__name__)

        router.add_url_rule(rule, 'handler', view_func=self.handler)

    @abstractmethod
    def handler(self):
        pass


class SlackEventAdapter(SlackAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handler(self):
        pass


class SlackInteractionsAdapter(SlackAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handler(self):
        pass
