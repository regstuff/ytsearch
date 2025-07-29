import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import smtplib, ssl # For emailer
from email.message import EmailMessage

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def search_recent_videos(api_key, query, min_view_count=500, time_delta_hours=24,
                         ignore_channels_by_id=None,
                         ignore_channels_by_name=None,
                         ignore_title_phrases=None,
                         no_ignore_channel_ids=None):
    ignore_ids = ignore_channels_by_id or []
    ignore_names_lower = [name.lower() for name in (ignore_channels_by_name or [])]
    ignore_phrases_lower = [phrase.lower() for phrase in (ignore_title_phrases or [])]
    no_ignore_ids = no_ignore_channel_ids or []
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=api_key)
        now = datetime.utcnow()
        time_ago = now - timedelta(hours=time_delta_hours)
        published_after_str = time_ago.isoformat("T") + "Z"
        print(f"Searching for videos published after: {published_after_str}\n")
        channel_videos = {}
        next_page_token = None
        while True:
            search_request = youtube.search().list(
                q=query,
                part='snippet',
                type='video',
                publishedAfter=published_after_str,
                maxResults=50,
                pageToken=next_page_token
            )
            search_response = search_request.execute()
            video_ids = [item['id']['videoId'] for item in search_response.get('items', []) if item['id']['kind'] == 'youtube#video']
            if video_ids:
                videos_list_request = youtube.videos().list(
                    part='snippet,statistics',
                    id=','.join(video_ids)
                )
                videos_list_response = videos_list_request.execute()
                videos_info = {item['id']: item for item in videos_list_response.get('items', [])}
            else:
                videos_info = {}
            for item in search_response.get('items', []):
                if item['id']['kind'] != 'youtube#video':
                    continue
                snippet = item['snippet']
                channel_id = snippet['channelId']
                channel_title = snippet['channelTitle']
                video_title = snippet['title']
                video_id = item['id']['videoId']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                if channel_id not in no_ignore_ids:
                    if channel_id in ignore_ids or channel_title.lower() in ignore_names_lower:
                        continue
                    title_lower = video_title.lower()
                    if any(phrase in title_lower for phrase in ignore_phrases_lower):
                        continue
                view_count = 0
                if video_id in videos_info and 'statistics' in videos_info[video_id]:
                    stats = videos_info[video_id]['statistics']
                    if 'viewCount' in stats:
                        try:
                            view_count = int(stats['viewCount'])
                        except ValueError:
                            view_count = 0
                if view_count < min_view_count:
                    continue
                video_data = {
                    'title': video_title,
                    'url': video_url,
                    'view_count': view_count
                }
                if channel_title not in channel_videos:
                    channel_videos[channel_title] = {
                        'channel_id': channel_id,
                        'videos': [video_data]
                    }
                else:
                    channel_videos[channel_title]['videos'].append(video_data)
            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                break
        return channel_videos
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {}

def azure_call(data):
    azure_url = os.environ["AZURE_URL"]
    azure_key = os.environ["AZURE_KEY"]
    azure_headers = {"Content-Type": "application/json", "api-key": azure_key}
    response = requests.post(azure_url, headers=azure_headers, json=data)
    if response.status_code == 200:
        # tokens can be logged if needed
        pass
    else:
        print('Azure API Error:', response.status_code, response.text)
        return 'FAILED'
    return response.json()['choices'][0]['message']['content']

def emailer_func(receiverlist, message, subj, senderid, port, mailpassword):
    context = ssl.create_default_context()
    msg = EmailMessage()
    msg['Subject'] = subj
    msg['To'] = receiverlist
    msg['From'] = senderid
    msg.set_content(message)
    with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
        server.login(senderid, mailpassword)
        server.send_message(msg)
    print('Email sent')

if __name__ == "__main__":
    # These must all be set in your github secrets/environment 
    search_query = os.environ["YT_QUERY"]
	org_query = os.environ["ORG_QUERY"] 
    API_KEY = os.environ["YOUTUBE_API_KEY"]
    MIN_VIEW_COUNT = int(os.environ.get("YT_MIN_VIEW_COUNT", "500"))
    EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]
    EMAIL_SENDER = os.environ["EMAIL_SENDER"]
    EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

    title_check_prompt = f"""INSTRUCTION: I will give you a social media video title. You must answer the question: Is the video related to {search_query}, founder of {org_query} & not about some other {search_query} or some totally unrelated topic?
The titles could be in non-English languages as well. Your answer must be either yes or no. Do not add anything else. When in doubt, err on the side of answering yes.
Title: """

    # same ignore lists as before. Optionally move to .env, or keep hardcoded.
    CHANNELS_NO_IGNORE_BY_ID = ['UC-DElHAqhzeTexoF7LrRcyw','UC3P015WGupr3J1EDYQoaWqw', 'UCsLDFHx31gPSuAe6ViDjGdg', 'UCwOr3bfCUy4hqX78ZwMlSAQ', 'UCn4DDzHQA9CqhL--ArCa1PA', 'UC_7cwhoVl0ZDpplpgk16w4A', 'UCVeALQJtRCs2GsnGQFv_Efg', 'UCLNsA4v3PHjH0C7u35mQTRw', 'UCu1lt1j_y5iy8LsA_MH-xVQ', 'UCnwW7lNw-VQNwPXwVXUJ1dA']
    CHANNELS_TO_IGNORE_BY_ID = [....]  # keep your big list here, omitted for brevity but same as your original
    CHANNELS_TO_IGNORE_BY_NAME = ["CNBC Television"]
    TITLE_PHRASES_TO_IGNORE = ['swamisamarth', 'samarth', 'saibaba', 'sai baba', 'aniruddhacharya', 'aniruddhacharyaji']
    
    videos_by_channel = search_recent_videos(
        API_KEY,
        search_query,
        min_view_count=MIN_VIEW_COUNT,
        ignore_channels_by_id=CHANNELS_TO_IGNORE_BY_ID,
        ignore_channels_by_name=CHANNELS_TO_IGNORE_BY_NAME,
        ignore_title_phrases=TITLE_PHRASES_TO_IGNORE,
        no_ignore_channel_ids=CHANNELS_NO_IGNORE_BY_ID
    )
    accepted_videos = []
    rejected_videos = []
    if videos_by_channel:
        print(f"--- Found {len(videos_by_channel)} channels. Filtering videos now.")
        for k, v in videos_by_channel.items():
            for video in v['videos']:
                title = video['title']
                data = {
                    "messages": [{"role":"user","content": title_check_prompt + title}],
                    "max_completion_tokens": 2,
                    "temperature": 1,
                    "frequency_penalty": 0,
                    "top_p": 0.95,
                    "stop": None
                }
                response = azure_call(data)
                if response.lower().strip() == 'yes':
                    accepted_videos.append({
                        'channel_name': k,
                        'channel_id': v['channel_id'],
                        'video_title': title,
                        'video_url': video['url'],
                        'view_count': video['view_count']
                    })
                else:
                    rejected_videos.append({
                        'channel_name': k,
                        'channel_id': v['channel_id'],
                        'video_title': title,
                        'video_url': video['url'],
                        'view_count': video['view_count']
                    })
    print(f"--- Found {len(accepted_videos)} accepted videos in total.")
    email_msg = ''
    for v in accepted_videos:
        email_msg += f'Channel name: {v["channel_name"]}\n'
        email_msg += f'Channel ID: {v["channel_id"]}\n'
        email_msg += f'Video title: {v["video_title"]}\n'
        email_msg += f'Video URL: {v["video_url"]}\n'
        email_msg += f'View Count: {v["view_count"]}\n'
        email_msg += '-----------\n'
    if email_msg:
        emailer_func(EMAIL_RECEIVER, email_msg, "AI Fake Video Check: Check if any of these videos are AI fakes", EMAIL_SENDER, 465, EMAIL_PASSWORD)
