import json
import logging
import os
import re
from datetime import datetime
from typing import List, Dict, Any

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"

# Constants for movie theater data
_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
_MOVIES_JSON = os.path.join(_DATA_PATH, "movies.json")
_SCHEDULES_JSON = os.path.join(_DATA_PATH, "schedules.json")
_SEAT_AVAILABILITY_JSON = os.path.join(_DATA_PATH, "seat_availability.json")
_RESERVATIONS_JSONL = os.path.join(_DATA_PATH, "reservations.jsonl")

# Common validation patterns
_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }


# Define the tool properties using the ToolProperty class
tool_properties_save_snippets_object = [
    ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet."),
    ToolProperty(_SNIPPET_PROPERTY_NAME, "string", "The content of the snippet."),
]
tool_properties_get_snippets_object = [ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet.")]

# Convert the tool properties to JSON
tool_properties_save_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_save_snippets_object])
tool_properties_get_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_get_snippets_object])


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> None:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_snippet",
    description="Retrieve a snippet by name.",
    toolProperties=tool_properties_get_snippets_json,
)
@app.generic_input_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def get_snippet(file: func.InputStream, context) -> str:
    """
    Retrieves a snippet by name from Azure Blob Storage.

    Args:
        file (func.InputStream): The input binding to read the snippet from Azure Blob Storage.
        context: The trigger context containing the input arguments.

    Returns:
        str: The content of the snippet or an error message.
    """
    snippet_content = file.read().decode("utf-8")
    logging.info(f"Retrieved snippet: {snippet_content}")
    return snippet_content


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="save_snippet",
    description="Save a snippet with a name.",
    toolProperties=tool_properties_save_snippets_json,
)
@app.generic_output_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def save_snippet(file: func.Out[str], context) -> str:
    content = json.loads(context)
    snippet_name_from_args = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
    snippet_content_from_args = content["arguments"][_SNIPPET_PROPERTY_NAME]

    if not snippet_name_from_args:
        return "No snippet name provided"

    if not snippet_content_from_args:
        return "No snippet content provided"

    file.set(snippet_content_from_args)
    logging.info(f"Saved snippet: {snippet_content_from_args}")
    return f"Snippet '{snippet_content_from_args}' saved successfully"


# Utility functions for movie theater operations
def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Load JSON data from file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Failed to load JSON file {file_path}: {e}")
        raise


def validate_date_format(date_str: str) -> bool:
    """Validate date format (YYYY-MM-DD)."""
    return bool(_DATE_PATTERN.match(date_str))


def get_movies_for_date(date_str: str) -> List[str]:
    """Get movie IDs that have schedules for the specified date."""
    try:
        schedules = load_json_file(_SCHEDULES_JSON)
        movie_ids = {schedule["movie_id"] for schedule in schedules if schedule["date"] == date_str}
        return list(movie_ids)
    except Exception as e:
        logging.error(f"Failed to get movies for date {date_str}: {e}")
        return []


# Define tool properties for movie theater operations
tool_properties_get_movie_list = [
    ToolProperty("date", "string", "Screening date in YYYY-MM-DD format. If not specified, returns all currently showing movies"),
    ToolProperty("search_query", "string", "Keyword for partial movie title search"),
    ToolProperty("genre", "string", "Filter by genre"),
]
tool_properties_get_movie_list_json = json.dumps([prop.to_dict() for prop in tool_properties_get_movie_list])


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_movie_list",
    description="Get a list of currently showing movies. Supports filtering by date and partial search by movie title.",
    toolProperties=tool_properties_get_movie_list_json,
)
def get_movie_list(context) -> str:
    """
    Get a list of currently showing movies with optional filtering.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: JSON string containing the movie list or error message.
    """
    try:
        # Parse input arguments
        content = json.loads(context)
        arguments = content.get("arguments", {})
        
        date_filter = arguments.get("date")
        search_query = arguments.get("search_query")
        genre_filter = arguments.get("genre")
        
        # Validate date format if provided
        if date_filter and not validate_date_format(date_filter):
            return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})
        
        # Validate string lengths
        if search_query and len(search_query) > 100:
            return json.dumps({"error": "Search query too long. Maximum 100 characters."})
        
        if genre_filter and len(genre_filter) > 50:
            return json.dumps({"error": "Genre filter too long. Maximum 50 characters."})
        
        # Load movie data
        try:
            movies = load_json_file(_MOVIES_JSON)
        except Exception as e:
            return json.dumps({"error": "Failed to load movie data."})
        
        # Filter movies based on date if specified
        if date_filter:
            valid_movie_ids = get_movies_for_date(date_filter)
            movies = [movie for movie in movies if movie["movie_id"] in valid_movie_ids]
        
        # Filter by search query if specified
        if search_query:
            search_query_lower = search_query.lower()
            movies = [movie for movie in movies if search_query_lower in movie["title"].lower()]
        
        # Filter by genre if specified
        if genre_filter:
            movies = [movie for movie in movies if movie["genre"] == genre_filter]
        
        # Generate response
        response = {"movies": movies}
        return json.dumps(response, ensure_ascii=False)
        
    except Exception as e:
        logging.error(f"Error in get_movie_list: {e}")
        return json.dumps({"error": "Internal server error."})


def get_movie_id_by_title(title: str) -> str:
    """Get movie ID by title."""
    try:
        movies = load_json_file(_MOVIES_JSON)
        for movie in movies:
            if movie["title"] == title:
                return movie["movie_id"]
        return None
    except Exception as e:
        logging.error(f"Failed to get movie ID by title {title}: {e}")
        return None


def calculate_seat_summary(schedule_id: str) -> tuple:
    """Calculate available and total seat counts for a schedule."""
    try:
        seat_data = load_json_file(_SEAT_AVAILABILITY_JSON)
        for seat_info in seat_data:
            if seat_info["schedule_id"] == schedule_id:
                available_count = sum(len(row["available_numbers"]) for row in seat_info["available_seats"])
                occupied_count = sum(len(row["occupied_numbers"]) for row in seat_info["occupied_seats"])
                return available_count, available_count + occupied_count
        return 0, 0
    except Exception as e:
        logging.error(f"Failed to calculate seat summary for schedule {schedule_id}: {e}")
        return 0, 0


# Define tool properties for get_show_schedule
tool_properties_get_show_schedule = [
    ToolProperty("movie_id", "string", "Movie ID"),
    ToolProperty("movie_title", "string", "Movie title (can be used as alternative to movie_id)"),
    ToolProperty("date", "string", "Screening date in YYYY-MM-DD format"),
]
tool_properties_get_show_schedule_json = json.dumps([prop.to_dict() for prop in tool_properties_get_show_schedule])


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_show_schedule",
    description="Get screening schedule for a specified movie. Also returns seat availability information.",
    toolProperties=tool_properties_get_show_schedule_json,
)
def get_show_schedule(context) -> str:
    """
    Get screening schedule for a specified date with optional movie filtering.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: JSON string containing the schedule list or error message.
    """
    try:
        # Parse input arguments
        content = json.loads(context)
        arguments = content.get("arguments", {})
        
        movie_id = arguments.get("movie_id")
        movie_title = arguments.get("movie_title")
        date_filter = arguments.get("date")
        
        # Validate required date parameter
        if not date_filter:
            return json.dumps({"error": "Date parameter is required."})
        
        # Validate date format
        if not validate_date_format(date_filter):
            return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."})
        
        # Validate string lengths
        if movie_id and len(movie_id) > 20:
            return json.dumps({"error": "Movie ID too long. Maximum 20 characters."})
        
        if movie_title and len(movie_title) > 100:
            return json.dumps({"error": "Movie title too long. Maximum 100 characters."})
        
        # Resolve movie ID from title if needed
        if movie_title and not movie_id:
            movie_id = get_movie_id_by_title(movie_title)
            if not movie_id:
                return json.dumps({"error": "Movie not found."})
        
        # Load schedule data
        try:
            schedules = load_json_file(_SCHEDULES_JSON)
        except Exception as e:
            return json.dumps({"error": "Failed to load schedule data."})
        
        # Filter schedules by date (and movie_id if provided)
        filtered_schedules = []
        for schedule in schedules:
            if schedule["date"] == date_filter:
                if not movie_id or schedule["movie_id"] == movie_id:
                    filtered_schedules.append(schedule)
        
        # Load movie data to get movie titles
        try:
            movies = load_json_file(_MOVIES_JSON)
            movie_dict = {movie["movie_id"]: movie["title"] for movie in movies}
        except Exception as e:
            return json.dumps({"error": "Failed to load movie data."})
        
        # Enhance schedules with movie titles and seat availability
        enhanced_schedules = []
        for schedule in filtered_schedules:
            available_count, total_count = calculate_seat_summary(schedule["schedule_id"])
            
            enhanced_schedule = {
                "schedule_id": schedule["schedule_id"],
                "movie_id": schedule["movie_id"],
                "date": schedule["date"],
                "start_time": schedule["start_time"],
                "end_time": schedule["end_time"],
                "theater_id": schedule["theater_id"],
                "movie_title": movie_dict.get(schedule["movie_id"], "Unknown"),
                "available_seats_count": available_count,
                "total_seats_count": total_count
            }
            enhanced_schedules.append(enhanced_schedule)
        
        # Sort by start time
        enhanced_schedules.sort(key=lambda x: x["start_time"])
        
        # Generate response
        response = {"schedules": enhanced_schedules}
        return json.dumps(response, ensure_ascii=False)
        
    except Exception as e:
        logging.error(f"Error in get_show_schedule: {e}")
        return json.dumps({"error": "Internal server error."})


def get_schedule_by_id(schedule_id: str) -> dict:
    """Get schedule information by schedule ID."""
    try:
        schedules = load_json_file(_SCHEDULES_JSON)
        for schedule in schedules:
            if schedule["schedule_id"] == schedule_id:
                return schedule
        return None
    except Exception as e:
        logging.error(f"Failed to get schedule by ID {schedule_id}: {e}")
        return None


def get_seat_availability_by_schedule_id(schedule_id: str) -> dict:
    """Get seat availability data by schedule ID."""
    try:
        seat_data = load_json_file(_SEAT_AVAILABILITY_JSON)
        for seat_info in seat_data:
            if seat_info["schedule_id"] == schedule_id:
                return seat_info
        return None
    except Exception as e:
        logging.error(f"Failed to get seat availability by schedule ID {schedule_id}: {e}")
        return None


def get_movie_by_id(movie_id: str) -> dict:
    """Get movie information by movie ID."""
    try:
        movies = load_json_file(_MOVIES_JSON)
        for movie in movies:
            if movie["movie_id"] == movie_id:
                return movie
        return None
    except Exception as e:
        logging.error(f"Failed to get movie by ID {movie_id}: {e}")
        return None


# Define tool properties for get_seat_availability
tool_properties_get_seat_availability = [
    ToolProperty("schedule_id", "string", "Schedule ID you want to get the list of available seats"),
]
tool_properties_get_seat_availability_json = json.dumps([prop.to_dict() for prop in tool_properties_get_seat_availability])


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_seat_availability",
    description="Get detailed seat availability for a specified screening session.",
    toolProperties=tool_properties_get_seat_availability_json,
)
def get_seat_availability(context) -> str:
    """
    Get detailed seat availability for a specified screening session.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: JSON string containing the seat availability information or error message.
    """
    try:
        # Parse input arguments
        content = json.loads(context)
        arguments = content.get("arguments", {})
        
        schedule_id = arguments.get("schedule_id")
        
        # Validate required schedule_id parameter
        if not schedule_id:
            return json.dumps({"error": "schedule_id is required."})
        
        # Validate string length
        if len(schedule_id) > 20:
            return json.dumps({"error": "Schedule ID too long. Maximum 20 characters."})
        
        # Get schedule information
        schedule = get_schedule_by_id(schedule_id)
        if not schedule:
            return json.dumps({"error": "Schedule not found."})
        
        # Get movie information
        movie = get_movie_by_id(schedule["movie_id"])
        if not movie:
            return json.dumps({"error": "Movie not found."})
        
        # Get seat availability data
        seat_data = get_seat_availability_by_schedule_id(schedule_id)
        if not seat_data:
            return json.dumps({"error": "Seat data not available."})
        
        # Sort available seats by row (alphabetically) and seat numbers (ascending)
        available_seats = sorted(seat_data["available_seats"], key=lambda x: x["row"])
        for row in available_seats:
            row["available_numbers"] = sorted(row["available_numbers"])
        
        # Sort occupied seats by row (alphabetically) and seat numbers (ascending)
        occupied_seats = sorted(seat_data["occupied_seats"], key=lambda x: x["row"])
        for row in occupied_seats:
            row["occupied_numbers"] = sorted(row["occupied_numbers"])
        
        # Generate response
        response = {
            "schedule_info": {
                "schedule_id": schedule["schedule_id"],
                "movie_id": schedule["movie_id"],
                "date": schedule["date"],
                "start_time": schedule["start_time"],
                "end_time": schedule["end_time"],
                "theater_id": schedule["theater_id"],
                "movie_title": movie["title"]
            },
            "available_seats": available_seats,
            "occupied_seats": occupied_seats
        }
        
        return json.dumps(response, ensure_ascii=False)
        
    except Exception as e:
        logging.error(f"Error in get_seat_availability: {e}")
        return json.dumps({"error": "Internal server error."})


# Common validation patterns for seat reservation
_SEAT_ID_PATTERN = re.compile(r'^[A-Z]\d+$')


def validate_seat_id_format(seat_id: str) -> bool:
    """Validate seat ID format (e.g., A1, B2)."""
    return bool(_SEAT_ID_PATTERN.match(seat_id))


def generate_reservation_id() -> str:
    """Generate unique reservation ID."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    # Add a simple counter if needed (simplified for this implementation)
    return f"RES{timestamp}"


def check_seat_availability(schedule_id: str, seat_ids: List[str]) -> tuple:
    """Check if all specified seats are available for reservation."""
    try:
        seat_data = get_seat_availability_by_schedule_id(schedule_id)
        if not seat_data:
            return False, "Seat data not available."
        
        # Create a set of all available seats
        available_seats = set()
        for row in seat_data["available_seats"]:
            for seat_num in row["available_numbers"]:
                available_seats.add(f"{row['row']}{seat_num}")
        
        # Check if all requested seats are available
        for seat_id in seat_ids:
            if seat_id not in available_seats:
                return False, f"Seat {seat_id} is already occupied."
        
        return True, ""
    except Exception as e:
        logging.error(f"Failed to check seat availability: {e}")
        return False, "Failed to check seat availability."


def update_seat_availability(schedule_id: str, seat_ids: List[str]) -> bool:
    """Update seat availability by moving reserved seats from available to occupied."""
    try:
        # Load current seat data
        seat_data_list = load_json_file(_SEAT_AVAILABILITY_JSON)
        
        # Find the relevant schedule
        schedule_index = -1
        for i, seat_info in enumerate(seat_data_list):
            if seat_info["schedule_id"] == schedule_id:
                schedule_index = i
                break
        
        if schedule_index == -1:
            return False
        
        seat_info = seat_data_list[schedule_index]
        
        # Convert seat_ids to row and number mapping
        seats_to_move = {}
        for seat_id in seat_ids:
            row = seat_id[0]
            number = int(seat_id[1:])
            if row not in seats_to_move:
                seats_to_move[row] = []
            seats_to_move[row].append(number)
        
        # Update available_seats and occupied_seats
        for row_data in seat_info["available_seats"]:
            row = row_data["row"]
            if row in seats_to_move:
                # Remove seats from available
                row_data["available_numbers"] = [
                    num for num in row_data["available_numbers"] 
                    if num not in seats_to_move[row]
                ]
        
        for row_data in seat_info["occupied_seats"]:
            row = row_data["row"]
            if row in seats_to_move:
                # Add seats to occupied
                row_data["occupied_numbers"].extend(seats_to_move[row])
                row_data["occupied_numbers"] = sorted(row_data["occupied_numbers"])
        
        # Save updated data
        with open(_SEAT_AVAILABILITY_JSON, 'w', encoding='utf-8') as f:
            json.dump(seat_data_list, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logging.error(f"Failed to update seat availability: {e}")
        return False


def save_reservation_data(reservation_data: dict) -> bool:
    """Save reservation data to JSONL file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(_RESERVATIONS_JSONL), exist_ok=True)
        
        # Append to JSONL file
        with open(_RESERVATIONS_JSONL, 'a', encoding='utf-8') as f:
            f.write(json.dumps(reservation_data, ensure_ascii=False) + '\n')
        
        return True
    except Exception as e:
        logging.error(f"Failed to save reservation data: {e}")
        return False


# Define tool properties for reserve_seats
tool_properties_reserve_seats = [
    ToolProperty("schedule_id", "string", "Schedule ID"),
    ToolProperty("seat_ids", "array", "List of seat IDs to reserve"),
]
tool_properties_reserve_seats_json = json.dumps([prop.to_dict() for prop in tool_properties_reserve_seats])


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="reserve_seats",
    description="Reserve specified seats. Supports multiple seat reservations simultaneously.",
    toolProperties=tool_properties_reserve_seats_json,
)
def reserve_seats(context) -> str:
    """
    Reserve specified seats for a screening session.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: JSON string containing the reservation information or error message.
    """
    try:
        # Parse input arguments
        content = json.loads(context)
        arguments = content.get("arguments", {})
        
        schedule_id = arguments.get("schedule_id")
        seat_ids = arguments.get("seat_ids", [])
        
        # Validate required parameters
        if not schedule_id:
            return json.dumps({"error": "schedule_id is required."})
        
        if not seat_ids:
            return json.dumps({"error": "seat_ids is required."})
        
        # Validate string lengths and formats
        if len(schedule_id) > 20:
            return json.dumps({"error": "Schedule ID too long. Maximum 20 characters."})
        
        # Validate seat ID formats
        for seat_id in seat_ids:
            if not validate_seat_id_format(seat_id):
                return json.dumps({"error": f"Invalid seat ID format: {seat_id}."})
        
        # Get schedule information
        schedule = get_schedule_by_id(schedule_id)
        if not schedule:
            return json.dumps({"error": "Schedule not found."})
        
        # Get movie information
        movie = get_movie_by_id(schedule["movie_id"])
        if not movie:
            return json.dumps({"error": "Movie not found."})
        
        # Check seat availability
        seats_available, error_message = check_seat_availability(schedule_id, seat_ids)
        if not seats_available:
            return json.dumps({"error": error_message})
        
        # Generate reservation data
        reservation_id = generate_reservation_id()
        reservation_time = datetime.now().isoformat()
        
        reservation_data = {
            "reservation_id": reservation_id,
            "schedule_id": schedule_id,
            "seat_ids": seat_ids,
            "reservation_time": reservation_time,
            "status": "confirmed"
        }
        
        # Update seat availability (Transaction start)
        if not update_seat_availability(schedule_id, seat_ids):
            return json.dumps({"error": "Failed to save reservation data."})
        
        # Save reservation data
        if not save_reservation_data(reservation_data):
            # Rollback: This is simplified - in production, implement proper rollback
            return json.dumps({"error": "Failed to save reservation data."})
        
        # Generate response
        response = {
            "reservation": {
                "reservation_id": reservation_id,
                "schedule_id": schedule_id,
                "seat_ids": seat_ids,
                "reservation_time": reservation_time,
                "status": "confirmed"
            },
            "schedule_info": {
                "movie_id": schedule["movie_id"],
                "movie_title": movie["title"],
                "date": schedule["date"],
                "start_time": schedule["start_time"],
                "end_time": schedule["end_time"],
                "theater_id": schedule["theater_id"]
            },
            "message": f"Successfully reserved {len(seat_ids)} seat(s)."
        }
        
        return json.dumps(response, ensure_ascii=False)
        
    except Exception as e:
        logging.error(f"Error in reserve_seats: {e}")
        return json.dumps({"error": "Internal server error."})


# Utility function to get reservation by ID
def get_reservation_by_id(reservation_id: str) -> dict:
    """Get reservation data by reservation ID."""
    try:
        if not os.path.exists(_RESERVATIONS_JSONL):
            return None
        
        with open(_RESERVATIONS_JSONL, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    reservation = json.loads(line.strip())
                    if reservation.get("reservation_id") == reservation_id:
                        return reservation
        return None
    except Exception as e:
        logging.error(f"Failed to get reservation by ID: {e}")
        return None


# Define tool properties for get_reservation_details
tool_properties_get_reservation_details = [
    ToolProperty("reservation_id", "string", "Reservation ID"),
]
tool_properties_get_reservation_details_json = json.dumps([prop.to_dict() for prop in tool_properties_get_reservation_details])


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_reservation_details",
    description="Get detailed information for a reservation by reservation ID.",
    toolProperties=tool_properties_get_reservation_details_json,
)
def get_reservation_details(context) -> str:
    """
    Get detailed information for a reservation by reservation ID.

    Args:
        context: The trigger context containing the input arguments.

    Returns:
        str: JSON string containing the reservation details or error message.
    """
    try:
        # Parse input arguments
        content = json.loads(context)
        arguments = content.get("arguments", {})
        
        reservation_id = arguments.get("reservation_id")
        
        # Validate required reservation_id parameter
        if not reservation_id:
            return json.dumps({"error": "reservation_id is required."})
        
        # Validate string length
        if len(reservation_id) > 20:
            return json.dumps({"error": "Reservation ID too long. Maximum 20 characters."})
        
        # Get reservation data
        reservation = get_reservation_by_id(reservation_id)
        if not reservation:
            return json.dumps({"error": "Reservation not found."})
        
        # Get schedule information
        schedule = get_schedule_by_id(reservation["schedule_id"])
        if not schedule:
            return json.dumps({"error": "Schedule not found."})
        
        # Get movie information
        movie = get_movie_by_id(schedule["movie_id"])
        if not movie:
            return json.dumps({"error": "Movie not found."})
        
        # Generate seat details
        seat_details = []
        for seat_id in reservation["seat_ids"]:
            row = seat_id[0]
            number = int(seat_id[1:])
            seat_details.append({
                "seat_id": seat_id,
                "row": row,
                "number": number
            })
        
        # Sort seat details by row and number
        seat_details.sort(key=lambda x: (x["row"], x["number"]))
        
        # Generate response
        response = {
            "reservation": {
                "reservation_id": reservation["reservation_id"],
                "schedule_id": reservation["schedule_id"],
                "seat_ids": reservation["seat_ids"],
                "reservation_time": reservation["reservation_time"],
                "status": reservation["status"]
            },
            "schedule_info": {
                "movie_id": schedule["movie_id"],
                "movie_title": movie["title"],
                "date": schedule["date"],
                "start_time": schedule["start_time"],
                "end_time": schedule["end_time"],
                "theater_id": schedule["theater_id"]
            },
            "seat_details": seat_details
        }
        
        return json.dumps(response, ensure_ascii=False)
        
    except Exception as e:
        logging.error(f"Error in get_reservation_details: {e}")
        return json.dumps({"error": "Internal server error."})
