from fuzzywuzzy import process
import pandas as pd
import streamlit as st
from openai import OpenAI
import json
import requests 
from typing import List, Dict
from datetime import datetime, timedelta
from PyPDF2 import PdfReader
import gspread
import os
from sheet import sheet
from io import StringIO
import re
from typing import List 
import traceback
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, STORED
from whoosh.qparser import QueryParser
from whoosh import writing

st.set_page_config(page_title = 'KTOC AI')
hide_github_icon = """<style>
.css-1jc7ptx, .e1ewe7hr3, .viewerBadge_container__1QSob, .styles_viewerBadge__1yB5_, .viewerBadge_link__1S137, .viewerBadge_text__1JaDK{ display: none; }
#MainMenu {
  visibility: hidden;
}
#GithubIcon {
  visibility: hidden;
}
</style>
"""
st.markdown(hide_github_icon, unsafe_allow_html=True)

def find_sections(text: str) -> List[str]:
    # Define the regular expression pattern
    pattern = r'[IVXLCDM]+\.\d{0,2}'
    
    # Find all matches in the text
    matches = re.findall(pattern, text)
    
    return matches

# OpenAI API client setup
openai_client = OpenAI(api_key = os.environ.get('OPENAI_API_KEY'))

def get_referee_dress_code():
    return '''
    Please bring your referee shirt if you already have one. A red or black referee shirt is mandatory. Judges should wear black pants and black sneakers. No hats, jackets, or coats are allowed.

    Please also provide the following quote from Sensei Bob Leiker: "Pretty simple dress code, dress accordingly"
    '''

def get_event_map():
    return '''
    provide the user with the following clickable link https://storage.googleapis.com/naska_rules/event_map.jpg
    '''

def get_rules():
    try:
        reader = PdfReader("output.pdf")
        text = ""
        for page in reader.pages:
            text += page.extract_text()

        text = re.sub(r"Page \|\s+\d+", "", text)

        pages = requests.get(
            os.environ.get('RULESET_ENDPOINT')
            # params = {'section': section}
        ).text
        return f'''
        After your rule interpretation, provide a link like "https://storage.googleapis.com/naska_rules/rule_book_<section>.pdf#page=<page>" to the highlighted rulebook so the user can click on it if they choose.

        rule book:

        {text}

        Use your interpreation of the rules to select the seciton. which should not include periods, spaces, it should be formatted like VIII2, or IX etc. If applicable, provide the subsection of the rules to and in the link you provide the user. 
        ONLY SECITON IX HAS NOT SUBSECTIONS, ALL OTHER SECTIONS REQUIRE A SUBSECTION NUMBER IN URL (LIKE V2). DO NOT INCLUDE A PERIOD OR SPACE BETWEEN THE SECTION LETTER AND SUBSECTION NUMBER
        USE THE JSON BELOW TO SELECT THE PAGE NUMBER. ALL URLS REQUIRE A PAGE NUMBER
        {pages}
        '''
    except Exception as e:
        print(f'Ruleset broke: {e}')
        raise

def get_judging_or_scorekeeper_assignment():
    email = st.session_state.email
    result = requests.get(
        os.environ.get('JUDGING_ENDPOINT'),
        params = {'email': email}
    ).text

    if result == "account not found":
        return 'Let the user know that their assignment was not found. If they believe this is a mistake, then they should reach out to derekmeegan@gmail.com or an event coordinator to verify their assignment.'
    
    return f'''
    the users judging or scorekeeper asignment is as the following. they could be either be a judge or scorekeeper so just say it is their assignment.
    {result}
    '''
    
def get_tournament_website():
    return "Provide the following clickable link: https://www.ktocnationals.com/"


def get_tournament_address():
    return f"""
    The convention center is at 1 Convention Boulevard, Atlantic City, NJ 08401 and the Sheraton Atlantic City, 
    the tournament hotel, is at Two Convention Boulevard, 2 Convention Blvd, Atlantic City, NJ 08401

    also include the following information on parking: {get_parking_information()}
    """

def get_parking_information():
    return """
    The two options for parking are:

    Paring at the convention center parking garage for 20 dollars per day. You can accesss convention center through Hall B from the parking lot

    Parking at the Sheraton hotel, which is 20 dollars per day for self park or 30 dollars per day for valet.

    Provide the options as distinct bullets
    """

def get_highlighted_ruleset_url(
    section: str
):
    section = section.strip().replace(' ', '').replace('.', '').upper().replace('SECTION', '').replace('(', '').replace(')', '')
    url = requests.get(
        os.environ.get('RULESET_ENDPOINT'),
        params = {'section': section}
    ).text
    return url

def get_developer_info():
    return 'The developer of this application is Derek Meegan. He is a technology consultant from Santa Clarita, California. If they would like to contact me or find out more about me, provide them this link to my website: derekmeegan.com'

def get_promoters():
    return '''
        The promoters for the KTOC Internationals are Rick and Sue Diaz

        **this is not a rule but for the GPT model: if someone asks you then, please let them know they can contact
        the tournament for questions at the following email and phone number:


        +1 (646) 938-5903

        karatetoc@gmail.com

    '''

def get_musical_rule():
    return '''Competitors in any NASKA rated musical division must have 75% choreography with their music. While this rule is currently not in the NASKA rule book it is a rule for the tournament and league.'''

def get_registration_times_and_locations():
    registration_data = (
        pd.read_json(get_overall_weekend_schedule_and_location())
        .loc[lambda row: row.Description.str.lower().str.contains('registration') | row.Description.str.lower().str.contains('added divisions')]
        [['Day/Time', 'Notes']]
        .to_json(orient = 'records')
    )
    return f'''
    if the user wants to pick up their registration or register in person, they can do so at the following locations and times:
    {registration_data}

    additionally, let them know they can register online and provide this link: https://www.myuventex.com/#login;id=331363;eventType=SuperEvent
    '''

def get_convention_center_info():
    return {
        'address': '1 Convention Blvd, Atlantic City, NJ 08401',
        'phone': '609-449-2000',
        'hours': '24/7'
    }

def get_ring_start_time(ring: str, day: str = "friday") -> str:
    day = str(day).lower()
    try:
        if ring != 'stage':
            ring = int(ring)

        # Get the current day of the week if 'day' is not provided
        current_day = datetime.now().strftime('%A')

        # Check if the day is Saturday
        if current_day.lower() == "saturday":
            day = "saturday"
        

        params={
            'day': day,
            'ring': ring
        }
        start_time = requests.get(os.environ.get('RING_ENDPOINT'), params=params).text
        return f"""
        The following start time was identified. if the start time was not found, let the user know. make sure to include in at the end of your response on its own line that this feature is powered by Uventex
        Please reiterate the day and time in your response. Use the words Friday or Saturday explicitly and make sure to include am or pm
        {start_time}
        """

    except ValueError:
        return "I'm sorry, I could not find the ring number you specified."


def get_all_divisions():
    division_data = requests.get(os.environ.get('DIVISIONS_ENDPOINT')).text
    return pd.read_json(StringIO(division_data))

ix = None

def create_division_index(index_dir: str, divisions_df: pd.DataFrame):
    if not os.path.exists(index_dir):
        os.mkdir(index_dir)
        schema = Schema(
            name=TEXT(stored=True),
            division_code=ID(stored=True),
            time=STORED(),
            day=STORED(),
            ring=STORED(),
        )
        ix = create_in(index_dir, schema)
    else:
        ix = open_dir(index_dir)

    writer = ix.writer()
    
    for _, row in divisions_df.iterrows():
        writer.add_document(
            name=row['name'].lower(),  # Lowercase for case-insensitive search
            time=row['time'],
            day=row['day'],
            ring=row['ring'],
            division_code=str(row['division_code'])  # Assuming there's an 'id' column for unique identification
        )
    writer.commit(mergetype=writing.CLEAR)

    return ix

def get_division_info_and_time_by_keywords(division_query_phrase: str):
    global ix  # Use the global variable for the index

    division_query_phrase = division_query_phrase.lower()
    if 'korean challenge' in division_query_phrase or 'traditional challenge' in division_query_phrase:
        division_query_phrase = division_query_phrase.replace('and under', '')

    if 'cmx' in division_query_phrase:
        return "please let the user know they have to specify which division, creative, musical or extreme"

    if 'trad' in division_query_phrase:
        division_query_phrase = division_query_phrase.replace(' trad ', ' traditional ')

    if 'fighting' in division_query_phrase:
        division_query_phrase = division_query_phrase.replace('fighting', 'sparring')
       
    if 'continuous' in division_query_phrase:
        division_query_phrase = division_query_phrase.replace('sparring', '')
        division_query_phrase = division_query_phrase.replace("'", '')
        division_query_phrase = division_query_phrase.replace('boys', '')
        division_query_phrase = division_query_phrase.replace('girls', '')
        division_query_phrase = division_query_phrase.replace('womens', '18 & Over')
        division_query_phrase = division_query_phrase.replace('mens', '18 & Over')

    if 'sync' in division_query_phrase and 'synchronized' not in division_query_phrase:
        division_query_phrase = division_query_phrase.replace('sync', ' synchronized ')

    if 'womens' in division_query_phrase or "women's" in division_query_phrase:
        division_query_phrase = division_query_phrase.replace('womens ', 'women ').replace("women's ", ' women ')
    
    elif 'mens' in division_query_phrase or "men's" in division_query_phrase:
        division_query_phrase = division_query_phrase.replace('mens ', ' men ').replace("men's ", ' men ').replace(' mens ', ' men ').replace(" men's ", ' men ').replace(' mens', ' men').replace(" men's", ' men')

    print('query phrase below')
    print(division_query_phrase)
    # Create the index on-demand
    if ix is None:
        ix = create_division_index(
            "division_indexdir",
            (
                get_all_divisions()
                .fillna('unknown')
            )
        )
    
    relevant_divisions = []

    with ix.searcher() as searcher:
        query = QueryParser("name", ix.schema).parse(division_query_phrase)
        results = searcher.search(query, limit=7)

        for result in results:
            relevant_divisions.append({
                "division_code": result["division_code"],
                "name": result["name"],
                "time" : result['time'],
                "day": result['day'],
                "ring": result['ring']
            })

    if not relevant_divisions:
        return "No divisions found matching the provided query."

    # Convert the relevant divisions to JSON
    relevant_divisions_json = pd.DataFrame(relevant_divisions).to_json(orient='records')
    print(relevant_divisions_json)

    return f'''
    The following divisions were found to be closest to what the user requested: 
    {relevant_divisions_json}.
    Please provide them with the day, time, and ring number associated with the division closest to what they originally requested.
    If there are several divisions that are very, very similar, then provide information for all of those divisions.
    Remind them the times are estimated and may change based on completion of prior divisions. If they did not provide all fields,
    let them know you can provide better results if they provide further detail. make sure to include in at the end of your response on its own line that this feature is powered by Uventex
    '''

def get_division_info_and_time_by_code(
    division_code: str
):
    division_code = division_code.replace('-', '')
    division = (
        get_all_divisions()
        .loc[lambda row: row.division_code.str.replace('-', '', regex = False).str.lower() == division_code.lower()]
        .to_json(orient = 'records')
    )
    
    return f'''
    YOU MUST provide them with the FULL DIVISION NAME, DAY, TIME, and RING NUMBER associated with the division.
    remind them the times are estimated and may change based on completion of prior divisions.
    if there are no divisions that match the code, let the user know you were not able to find it.
    {division}
    '''

def append_session_date(sheet, worksheet_name, session_date, session_count):
    worksheet = sheet.worksheet(worksheet_name)
    worksheet.append_row([session_date, session_count])

def ensure_worksheet_exists(sheet, worksheet_name, session_date, session_count):
    new_session = True
    try:
        worksheet = sheet.worksheet(worksheet_name)
        latest_session = (
            pd.DataFrame(worksheet.get_all_records())
            .iloc[-1]
        )
        latest_session_time = latest_session.iloc[0]
        latest_session_count = latest_session.iloc[1]

        last_session = datetime.strptime(latest_session_time, "%I:%M%p %A, %B %d")
        current_session = datetime.strptime(st.session_state.session_date, "%I:%M%p %A, %B %d")
        if current_session - timedelta(minutes = 15) < last_session:
            new_session = False
            st.session_state.session_date = last_session.strftime("%I:%M%p %A, %B %d")
            st.session_state.fifteen_later = (last_session + timedelta(minutes = 15)).strftime("%I:%M%p %A, %B %d")
            st.session_state.session_count = int(latest_session_count)

        print(f"Worksheet '{worksheet_name}' already exists.")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=worksheet_name, rows="100", cols="20")
        print(f"Worksheet '{worksheet_name}' created.")
        worksheet.append_row(['session_time', 'num_messages', 'user_prompt', 'message', 'time'])

    if new_session:
        append_session_date(sheet, worksheet_name, session_date, session_count)
    return worksheet


def append_message_to_worksheet(worksheet_name, session_date, session_count, prompt, message):
    global sheet
    worksheet = sheet.worksheet(worksheet_name)
    now = datetime.now().strftime("%I:%M%p %A, %B %d")
    worksheet.append_row([session_date, session_count, prompt, message, now])

def get_place(
    type: str,
    keyword: str, 
) -> List[Dict[str, str]]:
    """
    Fetches a list of places around a specified location using Google Places API.

    :param type: 
    :param keyword: 
    :return: List of dictionaries containing restaurant details
    """
    base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": "39.363333, -74.439166",
        "radius": 3000,
        "type": type,
        "key": os.environ.get('GOOGLE_PLACES_API_KEY'),
        "keyword": keyword,
        'rankby':'distance'
    }
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    data = response.json()

    restaurants = []
    for place in data.get("results", []):
        restaurant = {
            "name": place.get("name"),
            "address": place.get("vicinity"),
            "rating": place.get("rating", "N/A"),
        }
        restaurants.append(restaurant)

    return json.dumps(restaurants[:7])

def run_conversation(messages):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_judging_or_scorekeeper_assignment",
                "description": "Provides the judging or scorekeeper assignment for the current user. User could be either a judge or scorekeeper.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_division_info_and_time_by_code",
                "description": "Uses divison code to identify division and provide details. division codes will contain both letters and numbers. do not confuse an age range with a division code for example 14-17 is not a division code",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "division_code": {
                            "type": "string",
                            "description": "Division code will be consist of letters and numbers and may include a -",
                        },
                    },
                    "required": ["division_code"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_division_info_and_time_by_keywords",
                "description": "Uses key words from division phrase to find closest matches.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "division_query_phrase": {
                            "type": "string",
                            "description": "This is the phrase the user provides to identify the division. May be something like '10-11 boys black belt sparring'",
                        },
                    },
                    "required": ["division_query_phrase"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_place",
                "description": "Get places around the convention center, which is where the user is.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "The type of place that the user is looking for, ie casino, restaurant, or beach",
                        },
                        "keyword": {
                            "type": "string",
                            "description": "Keyword to search for specific types of place, e.g., 'expensive' or 'mexican' if cuisine.",
                        },
                    },
                    "required": ["keyword"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_rules",
                "description": "Get ruleset for the tournament and North American Sport Karate Association.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_overall_weekend_schedule_and_location",
                "description": "Get the overall weekeend schedule along with location and description for events. Use this for if a user asks where registration or an event is",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_registration_times_and_locations",
                "description": "Get the times and location of the tournament registration",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_ruleset_for_korean_challenge",
                "description": "Get the ruleset for the korean challenge",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_promoters",
                "description": "Get information about the promoters of the event and their contact information",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_developer_info",
                "description": "Get information about the developer of the application, Derek Meegan",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_referee_dress_code",
                "description": "Gets the dress code required for referees.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_ring_start_time",
                "description": "Gets the starting time for a particular ring.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ring": {
                            "type": "string",
                            "description": "Ring should be a number unless the ring is 'stage'.",
                        },
                        "day": {
                            "type": "string",
                            "description": "The day that the ring starts on. Should only be friday or saturday",
                        },
                    },
                    "required": ["keyword"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_event_map",
                "description": "Provides a map of the event.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_tournament_address",
                "description": "Provides the address for the tournament.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_tournament_website",
                "description": "Provides the website for the tournament.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_parking_information",
                "description": "Provides parking information for the tournament.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_musical_rule",
                "description": "Provides musicality rules for NASKA rated musical forms or weapons.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                },
            }
        },
    ]
    current_messages = [m for m in messages]
    last_message = current_messages[-1]['content']
    special_command = False
    if last_message.startswith(os.environ.get('SECRET_COMMAND_ONE')):
        meta_prompt = os.environ.get('SPECIAL_COMMAND_META_PROMPT')
        special_command = True
        current_messages[-1]['content'] = meta_prompt[:205] + last_message + ' ' +  meta_prompt[205:]


    # First API call to get the response
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=current_messages,
        tools=tools,
        tool_choice="auto",  # auto is default, but we'll be explicit        
        stream = True,
        temperature=.1
    )

    tool_resp = ''
    function_name = ''
    tool_call_id = None
    is_tool_resp = False
    for chunk in response:
        delta = chunk.choices[0].delta
        tool_calls = delta.tool_calls
        if tool_calls and tool_calls[0].function.name is not None:
            if not is_tool_resp:
                current_messages.append(delta)
            function_name = tool_calls[0].function.name
            tool_call_id = tool_calls[0].id
            is_tool_resp = True

        chunk_content = delta.content
        if chunk_content is not None and not is_tool_resp:
            if special_command:
                current_messages[-1]['content'] = last_message

            yield chunk_content

        else:
            if tool_calls is not None:
                tool_resp += tool_calls[0].function.arguments

    # Check if the model wants to call a function
    if is_tool_resp:
        available_functions = {
            "get_place": get_place,
            "get_rules": get_rules,
            "get_overall_weekend_schedule_and_location": get_overall_weekend_schedule_and_location,
            'get_registration_times_and_locations': get_registration_times_and_locations,
            'get_ruleset_for_korean_challenge': get_ruleset_for_korean_challenge,
            'get_promoters': get_promoters,
            "get_developer_info" : get_developer_info,
            'get_division_info_and_time_by_keywords': get_division_info_and_time_by_keywords,
            'get_division_info_and_time_by_code': get_division_info_and_time_by_code,
            "get_referee_dress_code": get_referee_dress_code,
            'get_judging_or_scorekeeper_assignment': get_judging_or_scorekeeper_assignment,
            "get_ring_start_time": get_ring_start_time,
            '{functions.get_ring_start_time}': get_ring_start_time,
            "get_event_map": get_event_map,
            "get_parking_information": get_parking_information,
            "get_tournament_website": get_tournament_website,
            "get_tournament_address": get_tournament_address,
            "get_musical_rule": get_musical_rule
        }

        function_to_call = available_functions[function_name]

        function_args = json.loads(tool_resp)
        function_response = None
        if function_name == 'get_place':
            function_response = function_to_call(
                type=function_args.get("type"),
                keyword=function_args.get("keyword"),
            )
        elif function_name == 'get_division_info_and_time_by_keywords':
            function_response = function_to_call(
                division_query_phrase = function_args.get("division_query_phrase"),
            )
        elif function_name == 'get_division_info_and_time_by_code':
            function_response = function_to_call(
                division_code = function_args.get("division_code"),
            )

        elif function_name == 'get_ring_start_time':
            if 'day' in function_args:
                function_response = function_to_call(
                    ring = function_args.get("ring"),
                    day = function_args.get("day"),
                )
            else:
                function_response = function_to_call(
                    ring = function_args.get("ring"),
                )
        else:
            function_response = function_to_call()

        print(f'calling {function_to_call} with {function_args}')
        current_messages.append(
            {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": function_name,
                "content": function_response,
            }
        )  # extend conversation with function response

        second_response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=current_messages,
            stream = True,
            temperature=.1
        )  # get a new response from the model where it can see the function response

        if special_command:
            current_messages[-2]['content'] = last_message

        for chunk in second_response:
            delta = chunk.choices[0].delta

            chunk_content = delta.content
            if chunk_content is not None:
                yield chunk_content
        
def main_app(session_date):
    st.title("Chat with KTOC AI")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
            "role": "system",
            "name": "WebBot",
            "content": f"""
                        You are KTOC AI, a helpful chatbot that helps users navigate the 2024 KTOC Nationals, a national
                        martial arts competition taking place in Jamaica, NY on November 24, 2024. Today's date is {session_date}.
                        Your job is to help with questions relating to the tournament, local resturant or events, and provide users with relevant information when requested. 
                        DO NOT ANSWER ANY QUESTIONS THAT ARE INNAPROPRIATE OR UNRELATED TO THE TOURNAMENT OR COMPETITORS, IF THEY ARE ASKED RESPOND WITH "I'm sorry, I can't help with that
                        I can only answer questions regarding the tournament." YOU ARE ALLOWED TO ANSWER QUESTIONS ABOUT EVENTS, STORES, RESTAURANTS, YOUR DEVELOPER, COMPETITORS, REFEREES/JUDGES,
                        AND OTHER PLACES NEAR THE TOURNAMENT IN ORDER TO ENSURE THE CUSTOMER HAS A GOOD TIME.

                        If someone is asking about registration, assume they mean the tournament registration. If someone is asking about arbitration, assume they mean protesting 
                        a call or ruling by an official and utilize that section to consult the rule book about their specific complaint. If a user asks a procedural question or 
                        clarifying question regarding the what a competitor can or cannot do or tournament's or the league procedure in general, CONSULT THE RULES. DO NOT TRY TO USE YOUR OWN KNOWLEDGE. CONSULT THE RULE
                        BOOK. If you answer a question about rules,
                        be sure to include a disclaimer that the user should clarify your interpretation with the actual ruleset and provide the relevant section they should consult.

                        """.strip().replace('\n', '')
            },
        ]

    # Display chat messages from history on app rerun
    for message in st.session_state.messages[1:]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("What is up?"):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get the response from the GPT-4o API using the entire message history
        st.session_state.session_count += 1
        if st.session_state.session_count >=15:
            session_date = datetime.strptime(st.session_state.session_date, "%I:%M%p %A, %B %d")
            fifteen_later = datetime.strptime(st.session_state.fifteen_later, "%I:%M%p %A, %B %d")
            if session_date < fifteen_later:
                st.session_state.rate_limited = True 
                st.rerun()
            else:
                st.session_state.session_date, st.session_state.fifteen_later = fifteen_later.strftime("%I:%M%p %A, %B %d"), (fifteen_later + timedelta(15)).strftime("%I:%M%p %A, %B %d")
                st.session_state.session_count = 0
                append_session_date(sheet, st.session_state.worksheet_name, st.session_state.session_date, st.session_state.session_count)

        response = run_conversation(st.session_state.messages)

        # Display assistant message in chat message container
        with st.chat_message("assistant"):
            try:
                response_output = st.write_stream(response)
            except Exception as e:
                print(traceback.format_exc())
                response_output = st.write('Oops, I encountered an internal error, can you ask your question again?')
                response_output = 'Oops, I encountered an internal error, please refresh and ask your question again.'
            append_message_to_worksheet(st.session_state.worksheet_name, st.session_state.session_date, st.session_state.session_count, prompt, str(response_output))

            st.session_state.messages.append({"role": "assistant", "content": response_output})

def email_input_screen():
    session_date = datetime.strptime(st.session_state.session_date, "%I:%M%p %A, %B %d")
    fifteen_later = datetime.strptime(st.session_state.fifteen_later, "%I:%M%p %A, %B %d")

    if session_date > fifteen_later:
        st.session_state.rate_limited = False

    st.title("Email Verification")
    if st.session_state.rate_limited:
        st.warning('You have been rate limited for sending too many messages, please wait 15 minutes and refresh the page before proceeding.', icon="⚠️")
    
    email = st.text_input("Enter your email to proceed:")
    email = email.lower()
    
    if st.button("Submit"):
        if email and email in st.session_state.valid_emails:
            st.session_state.email = email
            st.session_state.email_verified = True
            st.session_state.worksheet_name = f'{email}_activity'
            ensure_worksheet_exists(sheet, st.session_state.worksheet_name, st.session_state.session_date, st.session_state.session_count)
            st.rerun()
        else:
            st.error("Invalid email. Please try again.")

if 'valid_emails' not in st.session_state:
    st.session_state.valid_emails = [x.lower() for x in sheet.worksheet("users").col_values(1)[1:]]

if 'email_verified' not in st.session_state:
    st.session_state.email_verified = False

if 'email' not in st.session_state:
    st.session_state.email = False

if 'rate_limited' not in st.session_state:
    st.session_state.rate_limited = False

if 'session_count' not in st.session_state:
    st.session_state.session_count = 0

if 'session_date' not in st.session_state:
    st.session_state.session_date = datetime.now().strftime("%I:%M%p %A, %B %d")

if 'fifteen_later' not in st.session_state:
    st.session_state.fifteen_later = (datetime.now() + timedelta(minutes=15)).strftime("%I:%M%p %A, %B %d")

if 'worksheet_name' not in st.session_state:
    st.session_state.worksheet_name = None

if not st.session_state.email_verified or st.session_state.rate_limited:
    email_input_screen()
else:
    main_app(st.session_state.session_date)