# from aiogram.dispatcher.filters.state import State, StatesGroup


# class AdminStates(StatesGroup):
#     # Region states
#     waiting_region_name = State()
#     waiting_region_edit_name = State()
#     choosing_region_to_edit = State()
#     choosing_region_to_delete = State()
    
#     # District states
#     waiting_district_name = State()
#     waiting_district_edit_name = State()
#     choosing_region_for_district = State()
#     choosing_district_to_edit = State()
#     choosing_district_to_delete = State()
#     choosing_region_for_district_edit = State()

from aiogram.dispatcher.filters.state import State, StatesGroup

class AddRegionStates(StatesGroup):
    waiting_for_region_name = State()
    confirm_region = State()

class AddDistrictStates(StatesGroup):
    waiting_for_region_selection = State()
    waiting_for_district_name = State()
    confirm_district = State()