from aiogram.fsm.state import State, StatesGroup


class TaskUpdateState(StatesGroup):
    task_id = State()
    waiting_for_value = State()
    waiting_for_details = State()
    waiting_for_remarks = State()


class DailyRemarksState(StatesGroup):
    waiting_for_remarks = State()


class TaskRemarksState(StatesGroup):
    task_id = State()
    waiting_for_remarks = State()



class AddTaskState(StatesGroup):
    waiting_for_name = State()
    waiting_for_type = State()
    waiting_for_target = State()
    waiting_for_unit = State()
    waiting_for_points = State()
    waiting_for_time = State()


class EditTaskState(StatesGroup):
    task_id = State()
    field = State()
    waiting_for_value = State()


class SettingsTimeState(StatesGroup):
    time_type = State()  # morning, news, video, study, exercise, eod
    waiting_for_time = State()


class SettingsTimezoneState(StatesGroup):
    waiting_for_timezone = State()


class BroadcastState(StatesGroup):
    waiting_for_message = State()
