import pytest
from znatoks import check_answer

executor = 'teledima00'
nickname_expert_inf = 'inf777'
full_name_inf = 'vasilisa'

nickname_expert_sa = ''
full_name_expert_sa = 'санечка69'

nickname_expert_iryn = 'iryn'
full_name_expert_iryn = 'iryn95'


class TestClassCheckAnswer:
    def test_check_empty(self):
        assert check_answer([], executor, nickname_expert_inf, full_name_inf) == {'ok': False, 'cause': 'answer_user_not_found'}

    def test_check_i_only(self):
        assert check_answer(['teledima00'], executor, None, None) == {'ok': False, 'cause': 'same_user'}

    def test_check_other_expert(self):
        assert check_answer([nickname_expert_inf], executor, None, None) == {'ok': True, 'user': nickname_expert_inf}
        assert check_answer([nickname_expert_inf],
                            executor, nickname_expert_sa, None) == {'ok': False, 'cause': 'answer_user_not_found'}
        assert check_answer([nickname_expert_inf],
                            executor, nickname_expert_sa, full_name_expert_sa) == {'ok': False, 'cause': 'answer_user_not_found'}
        assert check_answer([full_name_expert_iryn], executor,
                            nickname_expert_iryn, full_name_expert_iryn) == {'ok': True, 'user': full_name_expert_iryn}

    def test_check_i_other_expert(self):
        assert check_answer([executor, nickname_expert_inf], executor, None, None) == \
               {'ok': False, 'cause': 'answer_user_not_found'}
        assert check_answer([executor, nickname_expert_inf], executor, nickname_expert_inf, full_name_inf) == {'ok': True, 'user': nickname_expert_inf}
        assert check_answer([executor, nickname_expert_inf], executor, executor, None) == {'ok': False, 'cause': 'same_user'}
        assert check_answer([executor, full_name_inf], executor, nickname_expert_inf, full_name_inf) == {'ok': True, 'user': full_name_inf}

    def test_check_others_experts(self):
        assert check_answer([nickname_expert_inf, full_name_expert_sa],
                            executor, nickname_expert_sa, full_name_expert_sa) == {'ok': True, 'user': full_name_expert_sa}
        assert check_answer([nickname_expert_inf, full_name_expert_sa],
                            executor, None, None) == {'ok': False, 'cause': 'answer_user_not_found'}

        assert check_answer([nickname_expert_inf, full_name_expert_sa],
                            executor, nickname_expert_inf, None) == {'ok': True, 'user': nickname_expert_inf}
        assert check_answer([nickname_expert_inf, full_name_expert_sa],
                            executor, nickname_expert_inf, full_name_inf) == {'ok': True, 'user': nickname_expert_inf}