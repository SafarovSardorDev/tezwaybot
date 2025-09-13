from aiogram.dispatcher.filters.state import State, StatesGroup

class RegionManagementStates(StatesGroup):
    main_menu = State()
    region_list = State()
    region_detail = State()
    waiting_for_edit_region_name = State()
    confirm_delete_region = State()
    waiting_for_new_region_name = State()
    confirm_add_region = State()

class DistrictManagementStates(StatesGroup):
    district_list = State()
    district_detail = State()
    waiting_for_edit_district_name = State()
    confirm_delete_district = State()
    waiting_for_new_district_name = State()
    confirm_add_district = State()