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
