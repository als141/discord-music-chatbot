from typing import Any, Optional, Type
import discord
import asyncio
from discord.ext.commands.help import HelpCommand
from openai import OpenAI
from discord.channel import VoiceChannel
from discord.player import FFmpegPCMAudio
from discord import app_commands
from discord.ext import commands
import yt_dlp as youtube_dl
import requests
from bs4 import BeautifulSoup
import urllib
import json
from discord.ext import commands
from collections import deque
import requests
from discord.ext import commands
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import spotdl
import os
from dotenv import load_dotenv
from config import channel_list
from config import system_prompt
from discord.app_commands import CommandTree
from discord import Intents, Interaction
import re
from discord import InteractionResponse
from googleapiclient.discovery import build
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()
DISCORD_TOKEN = os.getenv('REONA_TOKEN')
OPENAI_TOKEN = os.getenv('OPENAI_TOKEN')
MY_GUILD = os.getenv('MY_GUILD')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_API_KEY_2 = os.getenv('GOOGLE_API_KEY_2')
CUSTOM_SEARCH_ENGINE_ID = os.getenv('CUSTOM_SEARCH_ENGINE_ID')
RAPID_API_KEY = os.getenv('RAPID_API_KEY')
SPOTIFY_ID = os.getenv('SPOTIFY_ID')
SPOTIFY_SECRET = os.getenv('SPOTIFY_SECRET')

client_credentials_manager = spotipy.oauth2.SpotifyClientCredentials(SPOTIFY_ID, SPOTIFY_SECRET)
spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

clientai = OpenAI(
    api_key=OPENAI_TOKEN,
)
        
client = commands.Bot(
    command_prefix='!',
    case_insensitive=True,
    intents=discord.Intents.all()
)
# YTDLダウンローダー
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': './music/%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
# 音楽ファイルのクラス
class MusicFilePlayer(discord.FFmpegPCMAudio):
    def __init__(self, file_path, title, video_url):
        super().__init__(source=file_path)
        self.file_path = file_path
        self.title = title
        self.video_url = video_url
        self.related_videos = []

    async def get_image_url(self):
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(
            q=self.title,
            cx=CUSTOM_SEARCH_ENGINE_ID,
            searchType="image",
            num=1
        ).execute()
        image_url = res["items"][0]["link"]
        return image_url
    
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = ytdl.prepare_filename(data)
        return cls(filename, title=data.get('title', ''), video_url=url)
    
# アルバムアートのURLを取得する関数
async def get_track_art_url(track_title):
    search_result = spotify.search(track_title, limit=1)
    track_id = search_result['tracks']['items'][0]['id']
    track_info = spotify.track(track_id)
    if 'images' in track_info['album']:
        image_url = track_info['album']['images'][0]['url']
        print(image_url)
        return image_url
    else:
        return None
    
# プレイリスト操作関数 playlist.jsonには，ファイルパス，曲名，URL, アルバムアートのURLが保存されている．構成は，プレイリスト名，追加する曲の曲順，ファイルパス，曲名，URL, アルバムアートのURLとなる
# プレイリストに曲を追加
async def add_playlist(playlist_name, player: MusicFilePlayer):
    playlist_file = f"./playlists/{playlist_name}.json"
    with open(playlist_file, "r") as f:
        playlist = json.load(f)
    playlist.append({"file_path": player.file_path, "title": player.title, "video_url": player.video_url})
    with open(playlist_file, "w") as f:
        json.dump(playlist, f)
    return

# mymusicに保存されている楽曲をすべて表示する
async def show_mymusic(message: discord.Message):
    mymusic_dir = "./mymusic/"
    files = os.listdir(mymusic_dir)
    music_list = "\n".join([f"- {os.path.splitext(file)[0]}" for file in files])
    await message.reply(f"以下の楽曲が保存されています。\n```\n{music_list}\n```")
    return
    
async def extract_youtube_id(url):
    # YouTubeのURLからIDを抽出する正規表現
    pattern = r"(?<=v=)[a-zA-Z0-9_-]{11}(?=&|/|$)"
    match = re.search(pattern, url)
    if match:
        return match.group(0)
    else:
        return None

async def get_related_videos(player: MusicFilePlayer):
    related_videos_list = []
    if not player.video_url:
        related_videos_list.append({"url": "https://www.youtube.com/watch?v=pAgnrvo-hb4", "title": "エゴロック - すりぃ"})
        return related_videos_list
    video_id = await extract_youtube_id(player.video_url)
    url = "https://youtube-v31.p.rapidapi.com/search"
    querystring = {"relatedToVideoId":video_id,"part":"id,snippet","type":"video","maxResults":"10"}

    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "youtube-v31.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    json_data = response.json()
    for item in json_data["items"]:
        try:
            video_id = item["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            related_video_title = item["snippet"]["title"]
            related_videos_list.append({"url": video_url, "title": related_video_title})
        except KeyError:
            related_videos_list.append({"url": "https://www.youtube.com/watch?v=pAgnrvo-hb4", "title": "エゴロック - すりぃ"}) # videoIdが見つからない場合はこのアイテムをスキップ
        
    return related_videos_list

# 再生画面のUIクラス
class MusicPlayerView(discord.ui.View):
    def __init__(self, player: MusicFilePlayer, message):
        super().__init__()
        self.player = player
        self.message = message

    @discord.ui.button(label="スキップ", style=discord.ButtonStyle.red)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # スキップ処理をここに実装
        await interaction.response.defer()
        await skip_music(interaction.message)
        await interaction.followup.send("スキップしました", ephemeral=True)
        return
    
# 関連動画のセレクトメニューのUI
class RelatedVideosSelect(discord.ui.View):
    @discord.ui.select(cls=discord.ui.Select, custom_id="related_videos_select", placeholder="関連動画", min_values=1, max_values=1)
    async def selectMenu(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        # 選択された関連動画を再生する処理をここに実装
        video_url = select.values[0]
        player = await MusicFilePlayer.from_url(video_url)
        await interaction.followup.send("ダウンロード完了", ephemeral=True)
        await add_queue(player, interaction.message)
        if not interaction.guild.voice_client.is_playing():
            await play_next(interaction.message)
        return

# 音楽オブジェクトを保存するキュー
que = asyncio.Queue()

# ボイスチャンネル接続判定
async def check_voice_channel(message: discord.Message):
    if message.guild.voice_client is None:
        await message.reply('ボイスチャンネルに接続していません')
        return False
    else:
        return True
    
# spotifyダウンロードして，ダウンロードしたファイル名リストを返す
async def download_spotify(video_url, message: discord.Message):
    process = await asyncio.create_subprocess_shell(f"spotdl {video_url} --output ./spotifymusic/", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        output = stdout.decode()
        print(output)
        # スキップされた曲とダウンロードされた曲の名前を抽出する正規表現
        skipped_songs = re.findall(r"Skipping (.+?) \(file already exists\)", output)
        downloaded_songs = re.findall(r'Downloaded "(.+?)":', output)

        # すべての曲名を一つのリストに統合
        matches = skipped_songs + downloaded_songs
        file_names = [match for match in matches]
        print(f"ダウンロードしたファイル名: {file_names}")
    else:
        error_message = stderr.decode()
        await message.channel.send(f"エラーが発生しました： {error_message}")

    spotfy_directry = "./spotifymusic/"


    download_files =[]
    # MusicFilePlayerクラスのインスタンスを作成し、ダウンロードしたファイルの情報を保存
    for file_name in file_names:
        full_path = spotfy_directry + file_name + ".mp3"
        player = MusicFilePlayer(full_path, file_name, "")
        download_files.append(player)
    return download_files


# MusicPlayerViewインスタンスを作成し、UIを表示するコード
async def display_music_player_ui(player: MusicFilePlayer, message: discord.Message):
    track_info = player.title
    # image_url = await player.get_image_url()
    embed = discord.Embed(title="再生中の曲", description=track_info, color=discord.Color.blurple())
    image_url = await get_track_art_url(track_info)
    if image_url:
        embed.set_thumbnail(url=image_url)
    else:
        image_url = await player.get_image_url()
        embed.set_thumbnail(url=image_url)
    view = MusicPlayerView(player, message)
    await message.channel.send(embed=embed, view=view)
    select_view = RelatedVideosSelect()
    related_videos_list = await get_related_videos(player)
    for video in related_videos_list:
        select_view.selectMenu.add_option(label=video["title"], value=video["url"])
    await message.channel.send("次に再生したい動画を選択してください", view=select_view)
    return
# 音楽再生キューに曲を追加
async def add_queue(player: MusicFilePlayer, message: discord.Message):
    player = MusicFilePlayer(player.file_path, player.title, player.video_url)
    await message.reply("{}をキューに追加します。".format(player.title))
    await que.put(player)

# スキップ機能
async def skip_music(message: discord.Message):
    voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        return
    else:
        await message.reply('再生中の曲がありません。')
        return
    
async def search_youtube(query):
    youtube = build("youtube", "v3", developerKey=GOOGLE_API_KEY_2)
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        maxResults=1
    ).execute()
    video_id = search_response["items"][0]["id"]["videoId"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    return video_url

# フォルダ「mymusic」の中からワード検索（部分一致）し，該当すればそれをキューに追加し，該当しなければ該当する曲がない旨を返す
async def search_mymusic(query, message: discord.Message):
    mymusic_dir = "./mymusic/"
    files = os.listdir(mymusic_dir)
    for file in files:
        if query in file:
            player = MusicFilePlayer(f"{mymusic_dir}{file}", file, "")
            await add_queue(player, message)
            if not message.guild.voice_client.is_playing():
                await play_next(message)
            return
    await message.reply("該当する曲が見つかりませんでした")
    return

messages=[
    {"role": "system", "content": system_prompt},
]

async def play_next(message: discord.Message):
    if message.guild.voice_client.is_playing():
        return
    if que.empty():
        return
    player = await que.get()
    await display_music_player_ui(player, message)
    loop = asyncio.get_event_loop()
    message.guild.voice_client.play(player, after=lambda _:loop.create_task(play_next(message)))

@client.event
async def on_ready():
    print('ログインしました')
    await client.tree.sync()
    await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name='音楽再生が新しくなりました！'))
    return


@client.hybrid_command()
async def join(ctx):
    if ctx.guild.voice_client:
        return
    if ctx.author.voice is None:
        await ctx.reply("ボイスチャンネルに接続してください")
        return
    await ctx.author.voice.channel.connect()
    await ctx.reply("接続しました")
    return

@client.hybrid_command()
async def leave(ctx):
    if not await check_voice_channel(ctx):
        return
    await ctx.guild.voice_client.disconnect()
    await ctx.reply("切断しました")
    return

@client.hybrid_command()
async def skip(ctx):
    if not await check_voice_channel(ctx):
        return
    await skip_music(ctx)
    return

@client.hybrid_command()
async def queue(ctx):
    if que.empty():
        await ctx.reply("再生キューに曲がありません")
        return
    queue_list = []
    for item in que._queue:
        queue_list.append(item.title)
    embed = discord.Embed(title="再生キュー", description="\n".join(queue_list), color=discord.Color.blue())
    await ctx.reply(embed=embed)
    return

@client.hybrid_command()
@app_commands.describe(query="検索クエリ")
async def search(ctx, query: str):
    if not await check_voice_channel(ctx):
        return
    await search_mymusic(query, ctx)
    return

@client.hybrid_command()
async def mymusic(ctx):
    await show_mymusic(ctx)
    return

@client.hybrid_command()
async def reset(ctx):
    for i in range(len(messages)-1):
        messages.pop(1)
    await ctx.reply("リセットしました。")
    return

@client.hybrid_command()
async def yp(ctx, query: str):
    if not await check_voice_channel(ctx):
        return
    video_url = await search_youtube(query)
    process_msg = await ctx.reply("処理中です...")
    player = await MusicFilePlayer.from_url(video_url)
    await process_msg.delete()
    await add_queue(player, ctx)
    if not ctx.guild.voice_client.is_playing():
        await play_next(ctx)
    return


@client.event
async def on_message(message):
    # 再生関数
    if message.author.bot:
        return
    if message.channel.id not in channel_list:
        return
    if "!join" in message.content:
        msg = await message.reply("処理中です...")
        if message.guild.voice_client:
            await msg.delete()
            return
        if message.author.voice is None:
            await msg.delete()
            await message.channel.send("ボイスチャンネルに接続してください")
            return
        await message.author.voice.channel.connect()
        await msg.delete()
        return

    if "spotify" in message.content:
        if not await check_voice_channel(message):
            return
        video_url = message.content
        if "!next" in message.content:
            video_url = video_url.replace("!next", "")
        process_msg = await message.reply("処理中です...")
        download_files = await download_spotify(video_url, message)
        await process_msg.delete()
        for file in download_files:
            await add_queue(file, message)
        if not message.guild.voice_client.is_playing():
            await play_next(message)
        return
    
    if "http" in message.content:
        video_url = message.content
        if not await check_voice_channel(message):
            return
        if "!next" in message.content:
            video_url = video_url.replace("!next", "")
        if "!yp" in message.content:
            video_url = video_url.replace("!yp", "")
        process_msg = await message.reply("処理中です...")
        player = await MusicFilePlayer.from_url(video_url)
        await process_msg.delete()
        await add_queue(player, message)
        if not message.guild.voice_client.is_playing():
            await play_next(message)
        return
    
    if "!skip" in message.content:
        if not await check_voice_channel(message):
            return
        await skip_music(message)
        return
    
    if "!leave" in message.content:
        if not await check_voice_channel(message):
            return
        await message.guild.voice_client.disconnect()
        return
    
    if "!q" in message.content:
        if que.empty():
            await message.reply("再生キューに曲がありません")
            return
        queue_list = []
        for item in que._queue:
            queue_list.append(item.title)
        embed = discord.Embed(title="再生キュー", description="\n".join(queue_list), color=discord.Color.blue())
        await message.reply(embed=embed)
        return
    
    if "!yp" in message.content:
        if not await check_voice_channel(message):
            return
        query = message.content.replace("!yp", "")
        video_url = await search_youtube(query)
        process_msg = await message.reply("処理中です...")
        player = await MusicFilePlayer.from_url(video_url)
        await process_msg.delete()
        await add_queue(player, message)
        if not message.guild.voice_client.is_playing():
            await play_next(message)
        return
    
    if "!search" in message.content:
        if not await check_voice_channel(message):
            return
        query = message.content.replace("!search", "")
        process_msg = await message.reply("処理中です...")
        await search_mymusic(query, message)
        await process_msg.delete()
        return
    
    if "!reset" in message.content:
        for i in range(len(messages)-1):
            messages.pop(1)
        await message.reply("リセットしました。")
        return

    if "!mymusic" in message.content:
        await show_mymusic(message)
        return

    prompt = message.content
    messages.append({"role": "user", "content": prompt})
    response = clientai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=4096,
        temperature=1,
    )
    mes = response.choices[0].message
    while len(mes.content) > 0:
        if len(mes.content) > 2000:
            pos = mes.content[:2000].rfind("。")
            if pos == -1:
                pos = 2000
            await message.channel.send(mes.content[:pos])
            mes.content = mes.content[:pos]
        else:
            await message.channel.send(mes.content)
            mes.content = ""
    
    messages.append({"role": "assistant", "content": mes.content})
    return
        
client.run(DISCORD_TOKEN)
