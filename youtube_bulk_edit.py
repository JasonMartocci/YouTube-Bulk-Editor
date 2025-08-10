import re
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import pickle
import tkinter as tk
from tkinter import messagebox, scrolledtext, END, MULTIPLE, filedialog
from tkinter import ttk
import json
import time
import shutil  # For backing up tokens
import csv
import mimetypes

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# Brand colors - Enhanced with more options
BG_COLOR = '#f0f0f0'  # Light gray background
ACCENT_COLOR = '#FFD700'  # Gold yellow
BUTTON_BG = '#800000'  # Maroon
BUTTON_FG = '#FFFFFF'  # White text on buttons
TEXT_COLOR = '#000000'  # Black text
TEAL = '#00BFA5'  # Teal for highlights
ERROR_COLOR = '#FF0000'  # Red for errors
HEADER_COLOR = '#800000'  # Maroon for headers
SHADOW_COLOR = '#D3D3D3'  # Light gray for shadow effect

CATEGORIES = {
    '1': 'Film & Animation',
    '2': 'Autos & Vehicles',
    '10': 'Music',
    '15': 'Pets & Animals',
    '17': 'Sports',
    '18': 'Short Movies',
    '19': 'Travel & Events',
    '20': 'Gaming',
    '21': 'Videoblogging',
    '22': 'People & Blogs',
    '23': 'Comedy',
    '24': 'Entertainment',
    '25': 'News & Politics',
    '26': 'Howto & Style',
    '27': 'Education',
    '28': 'Science & Technology',
    '29': 'Nonprofits & Activism',
    '30': 'Movies',
    '31': 'Anime/Animation',
    '32': 'Action/Adventure',
    '33': 'Classics',
    '34': 'Comedy',
    '35': 'Documentary',
    '36': 'Drama',
    '37': 'Family',
    '38': 'Foreign',
    '39': 'Horror',
    '40': 'Sci-Fi/Fantasy',
    '41': 'Thriller',
    '42': 'Shorts',
    '43': 'Shows',
    '44': 'Trailers',
}

PRIVACY_STATUSES = ['public', 'private', 'unlisted']
LICENSES = ['youtube', 'creativeCommon']

def get_authenticated_service(token_file='token.pickle'):
    creds = None
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)
    return build('youtube', 'v3', credentials=creds)

def get_current_channel(youtube):
    try:
        request = youtube.channels().list(
            part="snippet",
            mine=True
        )
        response = request.execute()
        return response['items'][0]['snippet']['title']
    except Exception as e:
        return "Unknown (Error: " + str(e) + ")"

def get_uploads_playlist_id(youtube):
    request = youtube.channels().list(
        part="contentDetails",
        mine=True
    )
    response = request.execute()
    return response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

def get_all_videos(youtube, cache_file='videos_cache.json'):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            videos = json.load(f)
        return videos
    playlist_id = get_uploads_playlist_id(youtube)
    videos = []
    next_page_token = None
    while True:
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()
        for item in response['items']:
            vid = item['snippet']['resourceId']['videoId']
            snippet = item['snippet']
            videos.append({
                'id': vid,
                'title': snippet['title'],
                'description': snippet['description'],
                'tags': snippet.get('tags', []),
                'categoryId': snippet.get('categoryId', '22'),
                'defaultLanguage': snippet.get('defaultLanguage', ''),
            })
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    if videos:
        # Batch video IDs in groups of 50 to reduce API calls
        batch_size = 50
        for i in range(0, len(videos), batch_size):
            batch_ids = ','.join([v['id'] for v in videos[i:i + batch_size]])
            response = youtube.videos().list(
                part="snippet,status,recordingDetails",
                id=batch_ids
            ).execute()
            for item in response['items']:
                vid = item['id']
                for v in videos:
                    if v['id'] == vid:
                        v['categoryId'] = item['snippet'].get('categoryId', v['categoryId'])
                        v['defaultLanguage'] = item['snippet'].get('defaultLanguage', v['defaultLanguage'])
                        v['status'] = item['status']
                        v['recordingDate'] = item.get('recordingDetails', {}).get('recordingDate', '')
                        break
    with open(cache_file, 'w') as f:
        json.dump(videos, f)
    # Sort videos by title for better UX
    videos.sort(key=lambda x: x['title'].lower())
    return videos

def update_video(youtube, video_id, updates):
    body = {'id': video_id}
    if 'snippet' in updates:
        body['snippet'] = updates['snippet']
    if 'status' in updates:
        body['status'] = updates['status']
    if 'recordingDetails' in updates:
        body['recordingDetails'] = updates['recordingDetails']
    youtube.videos().update(
        part=','.join(updates.keys()),
        body=body
    ).execute()

def set_thumbnail(youtube, video_id, thumbnail_path):
    mime_type = mimetypes.guess_type(thumbnail_path)[0] or 'image/jpeg'
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path, mimetype=mime_type)
    ).execute()

def compute_new_desc(desc, action, footer, find, replace, keyword, trim_m, use_regex):
    new_desc = desc
    changed = False
    if action == "append":
        new_desc = desc + "\n\n" + footer
        changed = True
    elif action == "prepend":
        new_desc = footer + "\n\n" + desc
        changed = True
    elif action == "replace_all":
        new_desc = footer
        changed = True
    elif action == "find_replace":
        if find:
            if use_regex:
                new_desc = re.sub(find, replace, desc, flags=re.IGNORECASE)
            else:
                new_desc = desc.replace(find, replace)
            changed = new_desc != desc
    elif action == "trim":
        if keyword and trim_m != "none":
            if use_regex:
                match = re.search(keyword, desc, flags=re.IGNORECASE)
                if match:
                    if trim_m == "before":
                        new_desc = desc[match.start():]
                    elif trim_m == "after":
                        new_desc = desc[:match.end()]
                    changed = True
            else:
                parts = desc.partition(keyword)
                if parts[1]:
                    if trim_m == "before":
                        new_desc = parts[1] + parts[2]
                    elif trim_m == "after":
                        new_desc = parts[0] + parts[1]
                    changed = True
    elif action == "replace_after":
        if keyword:
            if use_regex:
                match = re.search(keyword, desc, flags=re.IGNORECASE)
                if match:
                    new_desc = desc[:match.end()] + footer
                    changed = True
            else:
                parts = desc.partition(keyword)
                if parts[1]:
                    new_desc = parts[0] + parts[1] + footer
                    changed = True
    return new_desc, changed

def compute_new_title(title, title_action, title_text):
    new_title = title
    changed = False
    if title_action == "append":
        new_title = title + " " + title_text
        changed = True
    elif title_action == "prepend":
        new_title = title_text + " " + title
        changed = True
    elif title_action == "replace":
        new_title = title_text
        changed = True
    return new_title, changed

def compute_new_tags(tags, tags_action, tags_text):
    new_tags = tags[:]
    changed = False
    if tags_action == "add":
        new_tags.extend([t.strip() for t in tags_text.split(',') if t.strip()])
        changed = True
    elif tags_action == "replace":
        new_tags = [t.strip() for t in tags_text.split(',') if t.strip()]
        changed = True
    elif tags_action == "remove":
        remove_set = set([t.strip() for t in tags_text.split(',') if t.strip()])
        new_tags = [t for t in new_tags if t not in remove_set]
        changed = True
    return new_tags, changed

if __name__ == '__main__':
    # GUI setup first, auth later
    root = tk.Tk()
    root.title("Martocci Mayhem YouTube Bulk Editor - @JasonMartocci")
    root.configure(bg=BG_COLOR)
    root.geometry("1400x900")

    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TButton", background=BUTTON_BG, foreground=BUTTON_FG, font=('Arial', 12, 'bold'), padding=10, relief='raised')
    style.map("TButton", background=[('active', '#A52A2A')])  # Darker maroon on hover
    style.configure("TRadiobutton", background=BG_COLOR, foreground=TEXT_COLOR, font=('Arial', 10, 'bold'))
    style.configure("TCheckbutton", background=BG_COLOR, foreground=TEXT_COLOR, font=('Arial', 10, 'bold'))
    style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=('Arial', 12, 'bold'))
    style.configure("Header.TLabel", foreground=HEADER_COLOR, font=('Arial', 14, 'bold underline'))
    style.configure("TEntry", fieldbackground='white', font=('Arial', 11))
    style.configure("TProgressbar", troughcolor=BG_COLOR, background=ACCENT_COLOR)
    style.configure("TFrame", relief='raised', borderwidth=2, background=BG_COLOR)
    style.configure("TNotebook", tabposition='n', background=BG_COLOR)
    style.configure("TNotebook.Tab", background=BUTTON_BG, foreground=BUTTON_FG, font=('Arial', 12, 'bold'), padding=[10, 5])
    style.map("TNotebook.Tab", background=[('selected', ACCENT_COLOR), ('active', TEAL)], foreground=[('selected', TEXT_COLOR)])

    # Brand header
    header_frame = ttk.Frame(root, style="TFrame")
    header_frame.pack(fill='x', pady=10)
    brand_label = ttk.Label(header_frame, text="Martocci Mayhem YouTube Bulk Editor", style="Header.TLabel")
    brand_label.pack(side='left', padx=20)
    channel_label = ttk.Label(header_frame, text="@JasonMartocci - Subscribe for More!", foreground=TEAL, font=('Arial', 12, 'italic'))
    channel_label.pack(side='left', padx=10)

    # Status label for account and quota
    status_frame = ttk.Frame(root)
    status_frame.pack(fill='x', pady=5)
    account_label = ttk.Label(status_frame, text="Account: Not connected", foreground=ERROR_COLOR)
    account_label.pack(side='left', padx=10)
    quota_label = ttk.Label(status_frame, text="Quota Status: Unknown", foreground=ERROR_COLOR)
    quota_label.pack(side='left', padx=10)
    switch_button = ttk.Button(status_frame, text="Switch Account", command=lambda: None)  # Define later
    switch_button.pack(side='left', padx=10)

    # Main paned window
    paned = ttk.PanedWindow(root, orient='horizontal')
    paned.pack(fill='both', expand=True)

    # Left pane for video list
    left_pane = ttk.Frame(paned)
    paned.add(left_pane, weight=1)
    left_canvas = tk.Canvas(left_pane, bg=BG_COLOR)
    left_scrollbar = ttk.Scrollbar(left_pane, orient="vertical", command=left_canvas.yview)
    left_frame = ttk.Frame(left_canvas, relief='raised', borderwidth=2)
    left_frame.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
    left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
    left_canvas.configure(yscrollcommand=left_scrollbar.set)
    left_canvas.pack(side='left', fill='both', expand=True)
    left_scrollbar.pack(side='right', fill='y')

    ttk.Label(left_frame, text="Search Videos:").pack(anchor='w', pady=5)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(left_frame, textvariable=search_var, width=60)
    search_entry.pack(fill='x')

    ttk.Label(left_frame, text="Select Videos:").pack(anchor='w', pady=5)
    video_list = tk.Listbox(left_frame, selectmode=MULTIPLE, height=30, width=60, font=('Arial', 11))
    video_list.pack(fill='both', expand=True)

    select_buttons_frame = ttk.Frame(left_frame)
    select_buttons_frame.pack(pady=10, fill='x')
    ttk.Button(select_buttons_frame, text="Select All", command=lambda: video_list.select_set(0, END)).pack(side='left', padx=5)
    ttk.Button(select_buttons_frame, text="Deselect All", command=lambda: video_list.selection_clear(0, END)).pack(side='left', padx=5)
    refresh_button = ttk.Button(select_buttons_frame, text="Refresh Videos")
    refresh_button.pack(side='left', padx=5)

    # Right pane for controls
    right_pane = ttk.Frame(paned)
    paned.add(right_pane, weight=2)
    right_canvas = tk.Canvas(right_pane, bg=BG_COLOR)
    right_scrollbar = ttk.Scrollbar(right_pane, orient="vertical", command=right_canvas.yview)
    right_frame = ttk.Frame(right_canvas, relief='raised', borderwidth=2)
    right_frame.bind("<Configure>", lambda e: right_canvas.configure(scrollregion=right_canvas.bbox("all")))
    right_canvas.create_window((0, 0), window=right_frame, anchor="nw")
    right_canvas.configure(yscrollcommand=right_scrollbar.set)
    right_canvas.pack(side='left', fill='both', expand=True)
    right_scrollbar.pack(side='right', fill='y')

    # Edit notebook
    edit_notebook = ttk.Notebook(right_frame)
    edit_notebook.pack(fill='x', pady=5)

    # Description tab
    desc_tab = ttk.Frame(edit_notebook, padding=10)
    edit_notebook.add(desc_tab, text='Description')

    action_frame = ttk.Frame(desc_tab, relief='groove', borderwidth=2)
    action_frame.pack(anchor='w', pady=5, padx=5)
    ttk.Label(action_frame, text="Action:").pack(anchor='w')
    action_var = tk.StringVar(value="append")
    ttk.Radiobutton(action_frame, text="Append", variable=action_var, value="append").pack(anchor='w')
    ttk.Radiobutton(action_frame, text="Prepend", variable=action_var, value="prepend").pack(anchor='w')
    ttk.Radiobutton(action_frame, text="Replace Entire", variable=action_var, value="replace_all").pack(anchor='w')
    ttk.Radiobutton(action_frame, text="Find & Replace", variable=action_var, value="find_replace").pack(anchor='w')
    ttk.Radiobutton(action_frame, text="Trim", variable=action_var, value="trim").pack(anchor='w')
    ttk.Radiobutton(action_frame, text="Replace After Keyword", variable=action_var, value="replace_after").pack(anchor='w')

    input_frame = ttk.Frame(desc_tab, relief='groove', borderwidth=2)
    input_frame.pack(fill='x', pady=5, padx=5)
    ttk.Label(input_frame, text="New Footer/Text:").grid(row=0, column=0, sticky='nw', pady=5, padx=5)
    footer_entry = tk.Text(input_frame, height=5, width=70, bg='white', fg=TEXT_COLOR, font=('Arial', 11))
    footer_entry.grid(row=0, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(input_frame, text="Find:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
    find_entry = ttk.Entry(input_frame, width=70)
    find_entry.grid(row=1, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(input_frame, text="Replace With:").grid(row=2, column=0, sticky='w', pady=5, padx=5)
    replace_entry = ttk.Entry(input_frame, width=70)
    replace_entry.grid(row=2, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(input_frame, text="Keyword:").grid(row=3, column=0, sticky='w', pady=5, padx=5)
    trim_keyword_entry = ttk.Entry(input_frame, width=70)
    trim_keyword_entry.grid(row=3, column=1, sticky='w', pady=5, padx=5)

    trim_mode_frame = ttk.Frame(input_frame)
    trim_mode_frame.grid(row=4, column=1, sticky='w', pady=5, padx=5)
    trim_mode = tk.StringVar(value="none")
    ttk.Radiobutton(trim_mode_frame, text="No Trim", variable=trim_mode, value="none").pack(side='left')
    ttk.Radiobutton(trim_mode_frame, text="Remove Before", variable=trim_mode, value="before").pack(side='left')
    ttk.Radiobutton(trim_mode_frame, text="Remove After", variable=trim_mode, value="after").pack(side='left')

    regex_var = tk.IntVar(value=0)
    ttk.Checkbutton(input_frame, text="Use Regex (Case Insensitive)", variable=regex_var).grid(row=5, column=1, sticky='w', pady=5, padx=5)

    # Title tab
    title_tab = ttk.Frame(edit_notebook, padding=10)
    edit_notebook.add(title_tab, text='Title')

    title_action_frame = ttk.Frame(title_tab, relief='groove', borderwidth=2)
    title_action_frame.pack(anchor='w', pady=5, padx=5)
    ttk.Label(title_action_frame, text="Title Action:").pack(anchor='w')
    title_action_var = tk.StringVar(value="none")
    ttk.Radiobutton(title_action_frame, text="No Change", variable=title_action_var, value="none").pack(anchor='w')
    ttk.Radiobutton(title_action_frame, text="Append", variable=title_action_var, value="append").pack(anchor='w')
    ttk.Radiobutton(title_action_frame, text="Prepend", variable=title_action_var, value="prepend").pack(anchor='w')
    ttk.Radiobutton(title_action_frame, text="Replace", variable=title_action_var, value="replace").pack(anchor='w')

    ttk.Label(title_tab, text="Title Text:").pack(anchor='w', pady=5, padx=5)
    title_entry = ttk.Entry(title_tab, width=70)
    title_entry.pack(fill='x', pady=5, padx=5)

    # Tags tab
    tags_tab = ttk.Frame(edit_notebook, padding=10)
    edit_notebook.add(tags_tab, text='Tags')

    tags_action_frame = ttk.Frame(tags_tab, relief='groove', borderwidth=2)
    tags_action_frame.pack(anchor='w', pady=5, padx=5)
    ttk.Label(tags_action_frame, text="Tags Action:").pack(anchor='w')
    tags_action_var = tk.StringVar(value="none")
    ttk.Radiobutton(tags_action_frame, text="No Change", variable=tags_action_var, value="none").pack(anchor='w')
    ttk.Radiobutton(tags_action_frame, text="Add (comma-separated)", variable=tags_action_var, value="add").pack(anchor='w')
    ttk.Radiobutton(tags_action_frame, text="Replace (comma-separated)", variable=tags_action_var, value="replace").pack(anchor='w')
    ttk.Radiobutton(tags_action_frame, text="Remove (comma-separated)", variable=tags_action_var, value="remove").pack(anchor='w')

    ttk.Label(tags_tab, text="Tags Text:").pack(anchor='w', pady=5, padx=5)
    tags_entry = ttk.Entry(tags_tab, width=70)
    tags_entry.pack(fill='x', pady=5, padx=5)

    # Status tab
    status_tab = ttk.Frame(edit_notebook, padding=10)
    edit_notebook.add(status_tab, text='Status')

    privacy_var = tk.StringVar(value="no_change")
    ttk.Label(status_tab, text="Privacy Status:").pack(anchor='w', pady=5, padx=5)
    ttk.Radiobutton(status_tab, text="No Change", variable=privacy_var, value="no_change").pack(anchor='w')
    for status in PRIVACY_STATUSES:
        ttk.Radiobutton(status_tab, text=status.capitalize(), variable=privacy_var, value=status).pack(anchor='w')

    license_var = tk.StringVar(value="no_change")
    ttk.Label(status_tab, text="License:").pack(anchor='w', pady=5, padx=5)
    ttk.Radiobutton(status_tab, text="No Change", variable=license_var, value="no_change").pack(anchor='w')
    for lic in LICENSES:
        ttk.Radiobutton(status_tab, text=lic.capitalize(), variable=license_var, value=lic).pack(anchor='w')

    embeddable_var = tk.StringVar(value="no_change")
    ttk.Label(status_tab, text="Embeddable:").pack(anchor='w', pady=5, padx=5)
    ttk.Radiobutton(status_tab, text="No Change", variable=embeddable_var, value="no_change").pack(anchor='w')
    ttk.Radiobutton(status_tab, text="Yes", variable=embeddable_var, value="true").pack(anchor='w')
    ttk.Radiobutton(status_tab, text="No", variable=embeddable_var, value="false").pack(anchor='w')

    public_stats_var = tk.StringVar(value="no_change")
    ttk.Label(status_tab, text="Public Stats Viewable:").pack(anchor='w', pady=5, padx=5)
    ttk.Radiobutton(status_tab, text="No Change", variable=public_stats_var, value="no_change").pack(anchor='w')
    ttk.Radiobutton(status_tab, text="Yes", variable=public_stats_var, value="true").pack(anchor='w')
    ttk.Radiobutton(status_tab, text="No", variable=public_stats_var, value="false").pack(anchor='w')

    made_for_kids_var = tk.StringVar(value="no_change")
    ttk.Label(status_tab, text="Self Declared Made For Kids:").pack(anchor='w', pady=5, padx=5)
    ttk.Radiobutton(status_tab, text="No Change", variable=made_for_kids_var, value="no_change").pack(anchor='w')
    ttk.Radiobutton(status_tab, text="Yes", variable=made_for_kids_var, value="true").pack(anchor='w')
    ttk.Radiobutton(status_tab, text="No", variable=made_for_kids_var, value="false").pack(anchor='w')

    # Category tab
    category_tab = ttk.Frame(edit_notebook, padding=10)
    edit_notebook.add(category_tab, text='Category')

    category_var = tk.StringVar()
    ttk.Label(category_tab, text="Category:").pack(anchor='w', pady=5, padx=5)
    category_combo = ttk.Combobox(category_tab, textvariable=category_var, values=['No Change'] + list(CATEGORIES.values()), state='readonly')
    category_combo.pack(fill='x', pady=5, padx=5)
    category_combo.set("No Change")

    # Thumbnail tab
    thumbnail_tab = ttk.Frame(edit_notebook, padding=10)
    edit_notebook.add(thumbnail_tab, text='Thumbnail')

    thumbnail_path_var = tk.StringVar()
    ttk.Label(thumbnail_tab, text="Thumbnail File Path:").pack(anchor='w', pady=5, padx=5)
    thumbnail_entry = ttk.Entry(thumbnail_tab, textvariable=thumbnail_path_var, width=70)
    thumbnail_entry.pack(fill='x', pady=5, padx=5)
    ttk.Button(thumbnail_tab, text="Browse", command=lambda: thumbnail_path_var.set(filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png")]))).pack(anchor='w', pady=5, padx=5)

    # Language tab
    language_tab = ttk.Frame(edit_notebook, padding=10)
    edit_notebook.add(language_tab, text='Language')

    language_var = tk.StringVar()
    ttk.Label(language_tab, text="Default Language (e.g., en):").pack(anchor='w', pady=5, padx=5)
    language_entry = ttk.Entry(language_tab, textvariable=language_var, width=70)
    language_entry.pack(fill='x', pady=5, padx=5)
    language_entry.insert(0, "No Change")

    # Recording date tab
    recording_tab = ttk.Frame(edit_notebook, padding=10)
    edit_notebook.add(recording_tab, text='Recording Date')

    recording_var = tk.StringVar()
    ttk.Label(recording_tab, text="Recording Date (ISO 8601, e.g., 2023-01-01T12:00:00Z):").pack(anchor='w', pady=5, padx=5)
    recording_entry = ttk.Entry(recording_tab, textvariable=recording_var, width=70)
    recording_entry.pack(fill='x', pady=5, padx=5)
    recording_entry.insert(0, "No Change")

    # Output notebook
    output_notebook = ttk.Notebook(right_frame)
    output_notebook.pack(fill='both', expand=True, pady=5)

    preview_frame = ttk.Frame(output_notebook, relief='groove', borderwidth=2)
    output_notebook.add(preview_frame, text='Preview')
    preview_text = scrolledtext.ScrolledText(preview_frame, height=15, width=80, bg='white', fg=TEXT_COLOR, font=('Arial', 11))
    preview_text.pack(fill='both', expand=True)

    log_frame = ttk.Frame(output_notebook, relief='groove', borderwidth=2)
    output_notebook.add(log_frame, text='Log')
    log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80, bg='white', fg=TEXT_COLOR, font=('Arial', 11))
    log_text.pack(fill='both', expand=True)

    # Bottom button frame
    button_frame = ttk.Frame(root, relief='raised', borderwidth=2)
    button_frame.pack(fill='x', pady=10)

    progress = ttk.Progressbar(button_frame, orient='horizontal', length=400, mode='determinate')
    progress.pack(fill='x', pady=5)

    backup_button = ttk.Button(button_frame, text="Backup")
    backup_button.pack(side='left', padx=10)
    restore_button = ttk.Button(button_frame, text="Restore")
    restore_button.pack(side='left', padx=10)
    preview_button = ttk.Button(button_frame, text="Preview")
    preview_button.pack(side='left', padx=10)
    update_button = ttk.Button(button_frame, text="Update")
    update_button.pack(side='left', padx=10)

    def save_log():
        file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if file:
            with open(file, 'w') as f:
                f.write(log_text.get(1.0, END))
            messagebox.showinfo("Info", "Log saved")

    save_log_button = ttk.Button(button_frame, text="Save Log", command=save_log)
    save_log_button.pack(side='left', padx=10)

    # Save/load settings
    settings_button_frame = ttk.Frame(button_frame)
    settings_button_frame.pack(side='left', padx=10)
    def save_settings():
        settings = {
            'action': action_var.get(),
            'footer': footer_entry.get(1.0, END).strip(),
            'find': find_entry.get(),
            'replace': replace_entry.get(),
            'keyword': trim_keyword_entry.get(),
            'trim_mode': trim_mode.get(),
            'use_regex': regex_var.get(),
            'title_action': title_action_var.get(),
            'title_text': title_entry.get(),
            'tags_action': tags_action_var.get(),
            'tags_text': tags_entry.get(),
            'privacy': privacy_var.get(),
            'license': license_var.get(),
            'embeddable': embeddable_var.get(),
            'public_stats': public_stats_var.get(),
            'made_for_kids': made_for_kids_var.get(),
            'category': category_var.get(),
            'thumbnail_path': thumbnail_path_var.get(),
            'language': language_var.get(),
            'recording_date': recording_var.get(),
        }
        with open('settings.json', 'w') as f:
            json.dump(settings, f)
        messagebox.showinfo("Info", "Settings saved")

    def load_settings():
        if os.path.exists('settings.json'):
            with open('settings.json', 'r') as f:
                settings = json.load(f)
            action_var.set(settings.get('action', 'append'))
            footer_entry.delete(1.0, END)
            footer_entry.insert(END, settings.get('footer', ''))
            find_entry.delete(0, END)
            find_entry.insert(0, settings.get('find', ''))
            replace_entry.delete(0, END)
            replace_entry.insert(0, settings.get('replace', ''))
            trim_keyword_entry.delete(0, END)
            trim_keyword_entry.insert(0, settings.get('keyword', ''))
            trim_mode.set(settings.get('trim_mode', 'none'))
            regex_var.set(settings.get('use_regex', 0))
            title_action_var.set(settings.get('title_action', 'none'))
            title_entry.delete(0, END)
            title_entry.insert(0, settings.get('title_text', ''))
            tags_action_var.set(settings.get('tags_action', 'none'))
            tags_entry.delete(0, END)
            tags_entry.insert(0, settings.get('tags_text', ''))
            privacy_var.set(settings.get('privacy', 'no_change'))
            license_var.set(settings.get('license', 'no_change'))
            embeddable_var.set(settings.get('embeddable', 'no_change'))
            public_stats_var.set(settings.get('public_stats', 'no_change'))
            made_for_kids_var.set(settings.get('made_for_kids', 'no_change'))
            category_var.set(settings.get('category', 'No Change'))
            thumbnail_path_var.set(settings.get('thumbnail_path', ''))
            language_var.set(settings.get('language', 'No Change'))
            recording_var.set(settings.get('recording_date', 'No Change'))
            messagebox.showinfo("Info", "Settings loaded")
        else:
            messagebox.showerror("Error", "No settings file found")

    ttk.Button(settings_button_frame, text="Save Settings", command=save_settings).pack(side='left', padx=5)
    ttk.Button(settings_button_frame, text="Load Settings", command=load_settings).pack(side='left', padx=5)

    # Export/import CSV
    csv_button_frame = ttk.Frame(button_frame)
    csv_button_frame.pack(side='left', padx=10)
    def export_csv():
        selected_indices = video_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "No videos selected")
            return
        selected_vids = []
        for idx in selected_indices:
            item = video_list.get(idx)
            vid_id = item.rsplit(' (', 1)[1][:-1]
            for v in videos:
                if v['id'] == vid_id:
                    selected_vids.append(v)
                    break
        file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file:
            with open(file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Title', 'Description', 'Tags', 'Category', 'Privacy'])
                for v in selected_vids:
                    writer.writerow([v['id'], v['title'], v['description'], ','.join(v['tags']), CATEGORIES.get(v['categoryId'], 'Unknown'), v['status']['privacyStatus']])
            messagebox.showinfo("Info", "Exported to CSV")

    def import_csv():
        file = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file:
            with open(file, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    vid_id, title, desc, tags, category, privacy = row
                    for v in videos:
                        if v['id'] == vid_id:
                            v['title'] = title
                            v['description'] = desc
                            v['tags'] = tags.split(',')
                            v['categoryId'] = next((k for k, val in CATEGORIES.items() if val == category), v['categoryId'])
                            v['status']['privacyStatus'] = privacy
                            break
            messagebox.showinfo("Info", "Imported from CSV")
            populate_video_list(videos)

    ttk.Button(csv_button_frame, text="Export CSV", command=export_csv).pack(side='left', padx=5)
    ttk.Button(csv_button_frame, text="Import CSV", command=import_csv).pack(side='left', padx=5)

    # Auth and load
    youtube = None
    videos = []
    cache_file = 'videos_cache.json'
    token_file = 'token.pickle'

    def populate_video_list(vids):
        video_list.delete(0, END)
        for v in vids:
            video_list.insert(END, f"{v['title']} ({v['id']})")

    def filter_videos(event=None):
        search_term = search_var.get().lower()
        video_list.delete(0, END)
        for v in videos:
            if search_term in v['title'].lower() or search_term in v['id']:
                video_list.insert(END, f"{v['title']} ({v['id']})")

    search_entry.bind("<KeyRelease>", filter_videos)

    def connect_account():
        global youtube, videos
        try:
            youtube = get_authenticated_service(token_file)
            account_label.config(text="Account: " + get_current_channel(youtube), foreground=TEAL)
            quota_label.config(text="Quota Status: OK", foreground=TEAL)
            videos = get_all_videos(youtube, cache_file)
            populate_video_list(videos)
            filter_videos()
        except Exception as e:
            error_msg = str(e)
            if "quotaExceeded" in error_msg:
                quota_label.config(text="Quota Status: Exceeded", foreground=ERROR_COLOR)
            else:
                account_label.config(text="Account: Error - " + error_msg, foreground=ERROR_COLOR)
            messagebox.showerror("Error", error_msg)

    def switch_account():
        if os.path.exists(token_file):
            shutil.copy(token_file, token_file + '.bak')  # Backup old token
        os.remove(token_file)
        connect_account()

    def refresh_videos():
        if youtube:
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                videos = get_all_videos(youtube, cache_file)
                populate_video_list(videos)
                filter_videos()
                log_text.insert(END, "Videos refreshed\n")
            except Exception as e:
                error_msg = str(e)
                log_text.insert(END, "Error refreshing videos: " + error_msg + "\n")
                if "quotaExceeded" in error_msg:
                    quota_label.config(text="Quota Status: Exceeded", foreground=ERROR_COLOR)
        else:
            messagebox.showwarning("Warning", "Connect account first")

    switch_button['command'] = switch_account
    refresh_button['command'] = refresh_videos

    # Backup function
    def backup():
        if youtube:
            try:
                backup_data = []
                batch_size = 50
                video_ids = [v['id'] for v in videos]
                for i in range(0, len(video_ids), batch_size):
                    batch_ids = ','.join(video_ids[i:i + batch_size])
                    response = youtube.videos().list(
                        part="snippet,status,recordingDetails",
                        id=batch_ids
                    ).execute()
                    for item in response['items']:
                        backup_data.append({
                            'id': item['id'],
                            'snippet': item['snippet'],
                            'status': item['status'],
                            'recordingDetails': item.get('recordingDetails', {})
                        })
                with open('backup.json', 'w') as f:
                    json.dump(backup_data, f)
                log_text.insert(END, "Backup saved to backup.json\n")
            except Exception as e:
                error_msg = str(e)
                log_text.insert(END, "Error during backup: " + error_msg + "\n")
                if "quotaExceeded" in error_msg:
                    quota_label.config(text="Quota Status: Exceeded", foreground=ERROR_COLOR)
        else:
            messagebox.showwarning("Warning", "Connect account first")

    # Restore function
    def restore():
        if youtube:
            if os.path.exists('backup.json'):
                with open('backup.json', 'r') as f:
                    backup_data = json.load(f)
                progress['maximum'] = len(backup_data)
                count = 0
                batch_size = 5
                for i in range(0, len(backup_data), batch_size):
                    batch = backup_data[i:i + batch_size]
                    for item in batch:
                        try:
                            updates = {
                                'snippet': item['snippet'],
                                'status': item['status'],
                                'recordingDetails': item['recordingDetails']
                            }
                            update_video(youtube, item['id'], updates)
                            for v in videos:
                                if v['id'] == item['id']:
                                    v.update({
                                        'title': item['snippet']['title'],
                                        'description': item['snippet']['description'],
                                        'tags': item['snippet'].get('tags', []),
                                        'categoryId': item['snippet'].get('categoryId'),
                                        'defaultLanguage': item['snippet'].get('defaultLanguage', ''),
                                        'status': item['status'],
                                        'recordingDate': item['recordingDetails'].get('recordingDate', '')
                                    })
                            log_text.insert(END, f"Restored {item['id']}\n")
                            count += 1
                            progress['value'] = count
                            root.update_idletasks()
                            time.sleep(1)
                        except Exception as e:
                            error_msg = str(e)
                            log_text.insert(END, f"Error restoring {item['id']}: {error_msg}\n")
                            if "quotaExceeded" in error_msg:
                                quota_label.config(text="Quota Status: Exceeded", foreground=ERROR_COLOR)
                log_text.see(END)
                progress['value'] = 0
            else:
                messagebox.showerror("Error", "No backup file found")
        else:
            messagebox.showwarning("Warning", "Connect account first")

    # Preview function
    def preview():
        if youtube:
            preview_text.delete(1.0, END)
            selected_indices = video_list.curselection()
            if not selected_indices:
                messagebox.showwarning("Warning", "No videos selected")
                return
            selected_vids = []
            for idx in selected_indices:
                item = video_list.get(idx)
                vid_id = item.rsplit(' (', 1)[1][:-1]
                for v in videos:
                    if v['id'] == vid_id:
                        selected_vids.append(v)
                        break
            footer = footer_entry.get(1.0, END).strip()
            find = find_entry.get().strip()
            replace = replace_entry.get().strip()
            keyword = trim_keyword_entry.get().strip()
            action = action_var.get()
            trim_m = trim_mode.get()
            use_regex = regex_var.get()
            title_action = title_action_var.get()
            title_text = title_entry.get().strip()
            tags_action = tags_action_var.get()
            tags_text = tags_entry.get().strip()
            category = next((k for k, v in CATEGORIES.items() if v == category_var.get()), None)
            privacy = privacy_var.get() if privacy_var.get() != "no_change" else None
            license_ = license_var.get() if license_var.get() != "no_change" else None
            embeddable = True if embeddable_var.get() == "true" else False if embeddable_var.get() == "false" else None
            public_stats = True if public_stats_var.get() == "true" else False if public_stats_var.get() == "false" else None
            made_for_kids = True if made_for_kids_var.get() == "true" else False if made_for_kids_var.get() == "false" else None
            thumbnail_path = thumbnail_path_var.get()
            language = language_var.get() if language_var.get() != "No Change" else None
            recording_date = recording_var.get() if recording_var.get() != "No Change" else None
            for v in selected_vids:
                preview_text.insert(END, f"{v['title']} ({v['id']}):\n")
                if title_action != "none":
                    new_title, _ = compute_new_title(v['title'], title_action, title_text)
                    preview_text.insert(END, f"New Title: {new_title}\n")
                if tags_action != "none":
                    new_tags, _ = compute_new_tags(v['tags'], tags_action, tags_text)
                    preview_text.insert(END, f"New Tags: {', '.join(new_tags)}\n")
                new_desc, desc_changed = compute_new_desc(v['description'], action, footer, find, replace, keyword, trim_m, use_regex)
                preview_text.insert(END, f"New Description: {new_desc}\n")
                if not desc_changed and action in ["trim", "find_replace", "replace_after"]:
                    preview_text.insert(END, "(No change - keyword not found?)\n")
                if category:
                    preview_text.insert(END, f"New Category: {CATEGORIES[category]}\n")
                if privacy:
                    preview_text.insert(END, f"New Privacy: {privacy}\n")
                if license_:
                    preview_text.insert(END, f"New License: {license_}\n")
                if embeddable is not None:
                    preview_text.insert(END, f"Embeddable: {embeddable}\n")
                if public_stats is not None:
                    preview_text.insert(END, f"Public Stats Viewable: {public_stats}\n")
                if made_for_kids is not None:
                    preview_text.insert(END, f"Made For Kids: {made_for_kids}\n")
                if thumbnail_path:
                    preview_text.insert(END, f"New Thumbnail: {thumbnail_path}\n")
                if language:
                    preview_text.insert(END, f"New Default Language: {language}\n")
                if recording_date:
                    preview_text.insert(END, f"New Recording Date: {recording_date}\n")
                preview_text.insert(END, "\n---\n\n")
            preview_text.see(END)
        else:
            messagebox.showwarning("Warning", "Connect account first")

    # Update function
    def update_videos():
        if youtube:
            if not messagebox.askyesno("Confirm", "Are you sure you want to update the selected videos?"):
                return
            selected_indices = video_list.curselection()
            if not selected_indices:
                messagebox.showwarning("Warning", "No videos selected")
                return
            selected_vids = []
            for idx in selected_indices:
                item = video_list.get(idx)
                vid_id = item.rsplit(' (', 1)[1][:-1]
                for v in videos:
                    if v['id'] == vid_id:
                        selected_vids.append(v)
                        break
            footer = footer_entry.get(1.0, END).strip()
            find = find_entry.get().strip()
            replace = replace_entry.get().strip()
            keyword = trim_keyword_entry.get().strip()
            action = action_var.get()
            trim_m = trim_mode.get()
            use_regex = regex_var.get()
            title_action = title_action_var.get()
            title_text = title_entry.get().strip()
            tags_action = tags_action_var.get()
            tags_text = tags_entry.get().strip()
            category = next((k for k, v in CATEGORIES.items() if v == category_var.get()), None)
            privacy = privacy_var.get() if privacy_var.get() != "no_change" else None
            license_ = license_var.get() if license_var.get() != "no_change" else None
            embeddable = True if embeddable_var.get() == "true" else False if embeddable_var.get() == "false" else None
            public_stats = True if public_stats_var.get() == "true" else False if public_stats_var.get() == "false" else None
            made_for_kids = True if made_for_kids_var.get() == "true" else False if made_for_kids_var.get() == "false" else None
            thumbnail_path = thumbnail_path_var.get()
            language = language_var.get() if language_var.get() != "No Change" else None
            recording_date = recording_var.get() if recording_var.get() != "No Change" else None
            batch_size = 5
            progress['maximum'] = len(selected_vids)
            count = 0
            for i in range(0, len(selected_vids), batch_size):
                batch = selected_vids[i:i + batch_size]
                for v in batch:
                    try:
                        updates = {}
                        snippet_updates = {}
                        status_updates = {}
                        recording_updates = {}
                        if title_action != "none":
                            new_title, _ = compute_new_title(v['title'], title_action, title_text)
                            snippet_updates['title'] = new_title
                        if tags_action != "none":
                            new_tags, _ = compute_new_tags(v['tags'], tags_action, tags_text)
                            snippet_updates['tags'] = new_tags
                        new_desc, _ = compute_new_desc(v['description'], action, footer, find, replace, keyword, trim_m, use_regex)
                        snippet_updates['description'] = new_desc
                        if category:
                            snippet_updates['categoryId'] = category
                        if language:
                            snippet_updates['defaultLanguage'] = language
                        if snippet_updates:
                            updates['snippet'] = snippet_updates
                        if privacy:
                            status_updates['privacyStatus'] = privacy
                        if license_:
                            status_updates['license'] = license_
                        if embeddable is not None:
                            status_updates['embeddable'] = embeddable
                        if public_stats is not None:
                            status_updates['publicStatsViewable'] = public_stats
                        if made_for_kids is not None:
                            status_updates['selfDeclaredMadeForKids'] = made_for_kids
                        if status_updates:
                            updates['status'] = status_updates
                        if recording_date:
                            recording_updates['recordingDate'] = recording_date
                            updates['recordingDetails'] = recording_updates
                        if updates:
                            update_video(youtube, v['id'], updates)
                        if thumbnail_path:
                            set_thumbnail(youtube, v['id'], thumbnail_path)
                        # Update local
                        if 'snippet' in updates:
                            v['title'] = updates['snippet'].get('title', v['title'])
                            v['description'] = updates['snippet'].get('description', v['description'])
                            v['tags'] = updates['snippet'].get('tags', v['tags'])
                            v['categoryId'] = updates['snippet'].get('categoryId', v['categoryId'])
                            v['defaultLanguage'] = updates['snippet'].get('defaultLanguage', v['defaultLanguage'])
                        if 'status' in updates:
                            v['status'].update(updates['status'])
                        if 'recordingDetails' in updates:
                            v['recordingDate'] = updates['recordingDetails'].get('recordingDate', v['recordingDate'])
                        log_text.insert(END, f"Updated {v['id']} successfully\n")
                        count += 1
                        progress['value'] = count
                        root.update_idletasks()
                        time.sleep(1)  # Delay to avoid rate limits
                    except Exception as e:
                        error_msg = str(e)
                        log_text.insert(END, f"Error updating {v['id']}: {error_msg}\n")
                        if "quotaExceeded" in error_msg:
                            quota_label.config(text="Quota Status: Exceeded!", foreground=ERROR_COLOR)
                log_text.see(END)
            progress['value'] = 0
            # Refresh list after update
            filter_videos()
        else:
            messagebox.showwarning("Warning", "Connect account first")

    backup_button['command'] = backup
    restore_button['command'] = restore
    preview_button['command'] = preview
    update_button['command'] = update_videos

    # Initial connect
    connect_account()

    root.mainloop() 