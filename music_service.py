import asyncio
import yt_dlp
import os
import glob
import re
from typing import Tuple, Optional, List, Dict


def search_music_sync(query: str, max_results: int = 8) -> Optional[List[Dict]]:
    """
    Ищет треки на YouTube без скачивания. Возвращает список результатов.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'noplaylist': True,
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)

            if 'entries' not in info or not info['entries']:
                return None

            results = []
            for entry in info['entries']:
                if entry is None:
                    continue
                duration = entry.get('duration', 0) or 0
                mins = int(duration) // 60
                secs = int(duration) % 60
                results.append({
                    'video_id': entry.get('id', ''),
                    'title': entry.get('title', 'Без названия'),
                    'uploader': entry.get('uploader', entry.get('channel', 'Неизвестен')),
                    'duration': duration,
                    'duration_str': f"{mins}:{secs:02d}",
                    'url': entry.get('webpage_url', ''),
                })
            return results if results else None
    except Exception as e:
        print(f"Ошибка при поиске: {e}")
        return None


def download_by_id_sync(video_id: str) -> Optional[Tuple[str, str, str, int]]:
    """
    Скачивает конкретное видео (аудио) по его ID.
    """
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            url = f"https://www.youtube.com/watch?v={video_id}"
            info = ydl.extract_info(url, download=True)

            # Находим скачанный файл
            matching_files = glob.glob(f"downloads/{video_id}.*")
            if matching_files:
                filename = matching_files[0]
            else:
                ext = info.get('ext', 'm4a')
                filename = f"downloads/{video_id}.{ext}"

            if not os.path.exists(filename):
                return None

            return (
                filename,
                info.get('title', 'Без названия'),
                info.get('uploader', 'Неизвестен'),
                info.get('duration', 0)
            )
    except Exception as e:
        print(f"Ошибка при скачивании: {e}")
        return None


# ========== Новые функции для скачивания по ссылке ==========

# Паттерны ссылок которые мы поддерживаем
URL_PATTERN = re.compile(
    r'https?://'
    r'(?:www\.)?'
    r'(?:'
    r'youtube\.com/watch|youtu\.be/|youtube\.com/shorts/'  # YouTube
    r'|music\.youtube\.com/'  # YouTube Music
    r'|tiktok\.com/|vm\.tiktok\.com/'  # TikTok
    r'|instagram\.com/(?:reel|p)/|instagr\.am/'  # Instagram
    r'|twitter\.com/|x\.com/'  # Twitter/X
    r'|vk\.com/video|vk\.com/clip'  # VK
    r'|soundcloud\.com/'  # SoundCloud
    r'|open\.spotify\.com/'  # Spotify (только метаданные)
    r'|music\.apple\.com/'  # Apple Music
    r'|reddit\.com/'  # Reddit
    r'|facebook\.com/.*video'  # Facebook
    r'|twitch\.tv/.*clip'  # Twitch clips
    r')'
    r'[^\s]+'
)


def is_supported_url(text: str) -> Optional[str]:
    """Проверяет, содержит ли текст поддерживаемую ссылку. Возвращает URL или None."""
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None


def download_audio_from_url_sync(url: str) -> Optional[Dict]:
    """
    Скачивает аудио по ссылке. Возвращает dict с информацией о файле.
    """
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': 'downloads/%(id)s_audio.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            video_id = info.get('id', 'unknown')
            matching_files = glob.glob(f"downloads/{video_id}_audio.*")
            if matching_files:
                filename = matching_files[0]
            else:
                ext = info.get('ext', 'm4a')
                filename = f"downloads/{video_id}_audio.{ext}"

            if not os.path.exists(filename):
                return None

            return {
                'filename': filename,
                'title': info.get('title', 'Без названия'),
                'uploader': info.get('uploader', info.get('channel', 'Неизвестен')),
                'duration': info.get('duration', 0) or 0,
                'video_id': video_id,
                'source': info.get('extractor', 'unknown'),
            }
    except Exception as e:
        print(f"Ошибка при скачивании аудио по ссылке: {e}")
        return None


def download_video_from_url_sync(url: str) -> Optional[Dict]:
    """
    Скачивает видео по ссылке. Возвращает dict с информацией о файле.
    Ограничение: до 50MB для телеграма.
    """
    ydl_opts = {
        'format': 'best[filesize<50M]/best[height<=720]/best',
        'outtmpl': 'downloads/%(id)s_video.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }

    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            video_id = info.get('id', 'unknown')
            # Ищем скачанный файл
            matching_files = glob.glob(f"downloads/{video_id}_video.*")
            if matching_files:
                filename = matching_files[0]
            else:
                ext = info.get('ext', 'mp4')
                filename = f"downloads/{video_id}_video.{ext}"

            if not os.path.exists(filename):
                return None

            # Проверяем размер файла (лимит Telegram ~50MB)
            file_size = os.path.getsize(filename)
            if file_size > 50 * 1024 * 1024:
                os.remove(filename)
                return None

            return {
                'filename': filename,
                'title': info.get('title', 'Без названия'),
                'uploader': info.get('uploader', info.get('channel', 'Неизвестен')),
                'duration': info.get('duration', 0) or 0,
                'video_id': video_id,
                'source': info.get('extractor', 'unknown'),
                'file_size': file_size,
            }
    except Exception as e:
        print(f"Ошибка при скачивании видео по ссылке: {e}")
        return None


# ========== Асинхронные обёртки ==========

async def search_music(query: str, max_results: int = 8) -> Optional[List[Dict]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, search_music_sync, query, max_results)


async def download_by_id(video_id: str) -> Optional[Tuple[str, str, str, int]]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, download_by_id_sync, video_id)


async def download_audio_from_url(url: str) -> Optional[Dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, download_audio_from_url_sync, url)


async def download_video_from_url(url: str) -> Optional[Dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, download_video_from_url_sync, url)


def get_original_track_query_sync(url: str) -> Optional[str]:
    """Пытается найти название оригинального трека из метаданных видео."""
    ydl_opts = {
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Не скачиваем, просто берем инфо
            info = ydl.extract_info(url, download=False)
            
            track = info.get('track')
            artist = info.get('artist')
            
            if track:
                if artist:
                    return f"{artist} - {track}"
                return track
            return None
    except Exception as e:
        print(f"Ошибка при поиске оригинального трека: {e}")
        return None


async def get_original_track_query(url: str) -> Optional[str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_original_track_query_sync, url)
