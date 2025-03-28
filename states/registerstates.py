from aiogram.dispatcher.filters.state import State, StatesGroup

class RegistrationForm(StatesGroup):
    role = State()
    first_name = State()
    last_name = State()
    phone_number = State()

class OrderState(StatesGroup):
    from_region = State()
    from_district = State()
    passengers = State()
    to_region = State()
    to_district = State()
    datetime = State()
    time = State()
    confirmation = State()