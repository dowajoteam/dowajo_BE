import os
import json

def get_openai_secret_key(filename='secrets.json', key='OPENAI_SECRET_KEY'):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(script_dir, filename)

    try:
        with open(file_path, 'r') as file:
            secrets = json.load(file)
        return secrets.get(key)
    except FileNotFoundError:
        print(f"The file {filename} was not found.")
        return None
    except json.JSONDecodeError:
        print(f"The file {filename} is not a valid JSON file.")
        return None


def get_naver_client_id(filename='secrets.json', key='NAVER_CLIENT_ID'):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(script_dir, filename)

    try:
        with open(file_path, 'r') as file:
            secrets = json.load(file)
        return secrets.get(key)
    except FileNotFoundError:
        print(f"The file {filename} was not found.")
        return None
    except json.JSONDecodeError:
        print(f"The file {filename} is not a valid JSON file.")
        return None

def get_naver_client_secret(filename='secrets.json', key='NAVER_CLIENT_SECRET'):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(script_dir, filename)

    try:
        with open(file_path, 'r') as file:
            secrets = json.load(file)
        return secrets.get(key)
    except FileNotFoundError:
        print(f"The file {filename} was not found.")
        return None
    except json.JSONDecodeError:
        print(f"The file {filename} is not a valid JSON file.")
        return None