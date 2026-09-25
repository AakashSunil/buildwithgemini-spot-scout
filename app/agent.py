# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.a2ui_utils import a2ui_callback
from app.geocoding import lookup_destination_coordinates
from app.image_gen import generate_parking_spot_visual
from app.parking_db import (
    add_parking_spot,
    calculate_parking_fee,
    check_spot_occupancy_status,
    get_parking_spot_details,
    list_supported_cities,
    search_parking_spots,
    update_spot_availability,
)

MODEL = "gemini-3.6-flash"


# WRITE: After each conversation turn, save durable preferences and facts to Memory Bank
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


def get_current_time(city: str = "San Francisco") -> str:
    """Gets the current local time for a city (defaults to San Francisco / America/Los_Angeles).

    Args:
        city: City name to look up time for.
    """
    tz = ZoneInfo("America/Los_Angeles")
    now = datetime.datetime.now(tz)
    return f"The current time in {city} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}."


_prompt_file = Path(__file__).parent / "a2ui_instructions.txt"
SPOT_SCOUT_A2UI_INSTRUCTIONS = _prompt_file.read_text(encoding="utf-8")

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=SPOT_SCOUT_A2UI_INSTRUCTIONS,
    tools=[
        PreloadMemoryTool(),
        lookup_destination_coordinates,
        generate_parking_spot_visual,
        search_parking_spots,
        check_spot_occupancy_status,
        get_parking_spot_details,
        calculate_parking_fee,
        add_parking_spot,
        update_spot_availability,
        list_supported_cities,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)


