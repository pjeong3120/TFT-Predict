import requests, time, os, pickle
from tqdm.notebook import tqdm
from collections import defaultdict
import pandas as pd
import numpy as np
import re

def get_resp(api_url):
    resp = requests.get(api_url)
    
    while resp.status_code == 429:
        time.sleep(float(resp.headers.get('Retry-After')) + 1)
        resp = requests.get(api_url)
    
    return resp

def get_player_puuids(rank, api_key):
    assert rank == 'challenger' or rank == 'master' or rank == 'grandmaster', "Invalid rank - please enter 'challenger', 'master', or 'grandmaster'."
    
    chall_url = f"https://na1.api.riotgames.com/tft/league/v1/{rank}?queue=RANKED_TFT&api_key={api_key}"
    resp = get_resp(chall_url)
    
    s_names = [player['summonerName'] for player in resp.json()['entries']]
    puuids = []
    
    for i in tqdm(range(len(s_names))):
        api_url = f"https://na1.api.riotgames.com/tft/summoner/v1/summoners/by-name/{s_names[i]}?api_key={api_key}"
        puuid = get_resp(api_url)
        if puuid.status_code != 200:
            continue
        puuids.append(puuid.json()['puuid'])
    return puuids

    

def get_match_ids(puuids, startTime, api_key):
    match_ids = set()
    bad_ids = []
    for i in tqdm(range(len(puuids))):
        match_api = f"https://americas.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuids[i]}/ids?start=0&count=200&api_key={api_key}"
        resp = get_resp(match_api)
        if resp.status_code != 200:
            bad_ids.append(p_id)
            continue
        for m_id in resp.json():
            match_ids.add(m_id)
    return match_ids


def get_match_data(match_ids, data_out, api_key, set_number = 10):
    data = []
    bad_ids = []

    os.mkdir(os.path.join(data_out, 'raw_data'))

    for i in tqdm(range(len(match_ids))):
        m_id = match_ids.pop()
        m_url = f"https://americas.api.riotgames.com/tft/match/v1/matches/{m_id}?api_key={api_key}"
        resp = get_resp(m_url)
        if resp.status_code != 200:
            bad_ids.append(m_id)
            continue
        resp = resp.json()['info']
        if resp['tft_set_number'] != set_number or resp['tft_game_type'] != 'standard': # filter out random bad games
            continue

        participants = resp['participants']
        
        top_two = sorted(participants, key = lambda p : p['placement'])[:2]
        data.append(top_two)

        if (i + 1) % 1000 == 0:
            pickle.dump(data, open(os.join(data_out, 'raw_data', f"data{i // 1000}.pkl"), 'wb'))
            data = []

    pickle.dump(data, open(os.path.join(data_out, 'raw_data', f"data{i // 1000}.pkl"), 'wb'))
    pickle.dump(bad_ids, open(os.path.join(data_out, 'raw_data', "bad_ids.pkl"), 'wb'))

    return data


def compile_data(dir):
    pattern = re.compile(r'data\d+\.pkl')

    if os.path.exists(os.path.join(dir, 'raw_data', 'data.pkl')):
        return pickle.load(open(os.path.join(dir, 'raw_data', 'data.pkl'), 'rb'))
    
    data = []
    for file in os.listdir(os.path.join(dir, 'raw_data')):
        if pattern.match(file):
            data = data + pickle.load(open(os.path.join(dir, 'raw_data', file), 'rb'))

    pickle.dump(data, open(os.path.join(dir, 'raw_data', 'data.pkl'), 'wb'))
    return data



def fit_features(data, get_match_vector, data_out, file_name = 'processed_data'):
    if os.path.exists(os.path.join(data_out, f'{file_name}.pkl')):
        return pickle.load(open(os.path.join(data_out, f'{file_name}.pkl'), 'rb'))
        
    data = data.copy()
    labels = np.random.randint(0, 2, size = len(data), dtype = int)

    for i in range(len(data)):
        if not labels[i]:
            temp = data[i][0]
            data[i][0] = data[i][1]
            data[i][1] = temp

    data_matrix = pd.DataFrame()
    data_matrix = pd.concat([get_match_vector(match[0], match[1]) for match in data], axis = 1, ignore_index = True).T
    data_matrix.fillna(0, inplace = True)

    pickle.dump((labels, data_matrix), open(os.path.join(data_out, f'{file_name}.pkl'), 'wb'))
    return labels, data_matrix

