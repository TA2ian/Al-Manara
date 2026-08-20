from states import AdminStates


def test_broadcast_states_are_distinct():
    assert AdminStates.waiting_broadcast != AdminStates.waiting_broadcast_preview


def test_admin_broadcast_state_names_are_explicit():
    assert AdminStates.waiting_broadcast.state.endswith(":waiting_broadcast")
    assert AdminStates.waiting_broadcast_preview.state.endswith(":waiting_broadcast_preview")
