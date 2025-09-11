from aiogram.dispatcher.filters.state import State, StatesGroup

class RegistrationForm(StatesGroup):
    role = State()
    first_name = State()
    last_name = State()
    phone_number = State()

class DriverState(StatesGroup):
    waiting_subscription = State()

class OrderState(StatesGroup):
    from_region = State()
    from_district = State()
    passengers = State()
    to_region = State()
    to_district = State()
    datetime = State()
    time = State()
    confirmation = State()

class EditProfile(StatesGroup):
    first_name = State()
    last_name = State()
    phone_number = State()

class ChangeRole(StatesGroup):
    role = State()

class HistoryState(StatesGroup):
    pagination = State()

class DeliveryState(StatesGroup):
    from_region = State()
    from_district = State()
    to_region = State()
    to_district = State()
    package_type = State()
    package_size = State()
    package_weight = State()
    package_description = State()
    receiver_name = State()
    receiver_phone = State()
    confirmation = State()