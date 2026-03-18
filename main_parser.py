import os
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from urllib.parse import urljoin
import hashlib
import json

# Настройки
BASE_URL = "https://my.tretyakov.ru"
START_PAGE = 1
END_PAGE = 497
SAVE_DIR = r"ПОЛНЫЙ_ПУТЬ_ДО_ПАПКИ_СОХРАНЕНИЯ"
IDS_FILE = os.path.join(SAVE_DIR, 'artwork_ids.txt')
PROGRESS_FILE = os.path.join(SAVE_DIR, 'download_progress.json')

# Создаем папку
os.makedirs(SAVE_DIR, exist_ok=True)

# Сессия
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})


def make_request(url, max_retries=3):
    """Безопасный запрос с повторными попытками"""
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response
        except Exception as e:
            if attempt < max_retries - 1:
                wait = random.uniform(2, 5)
                print(f"  ⏳ Ошибка, жду {wait:.1f} сек...")
                time.sleep(wait)
            else:
                print(f"  ❌ Не удалось загрузить: {url}")
                return None
    return None


def collect_all_ids():
    """Собирает все ID картин со всех страниц"""
    print("=" * 70)
    print("🔄 СБОР ВСЕХ ID КАРТИН")
    print("=" * 70)

    all_ids = set()  # Используем set для избежания дубликатов

    # Проверяем, есть ли уже сохраненные ID
    if os.path.exists(IDS_FILE):
        print(f"📁 Найден файл с ID: {IDS_FILE}")
        try:
            with open(IDS_FILE, 'r', encoding='utf-8') as f:
                existing_ids = set(line.strip() for line in f if line.strip())
            if existing_ids:
                print(f"📊 Загружено {len(existing_ids)} ID из файла")
                all_ids.update(existing_ids)

                # Спросим пользователя, нужно ли обновить
                choice = input("🔄 Обновить список ID (скачать заново)? (y/n): ").lower()
                if choice != 'y':
                    return list(all_ids)
                else:
                    all_ids = set()
        except:
            pass

    for page_num in range(START_PAGE, END_PAGE + 1):
        print(f"\n📄 Страница {page_num}/{END_PAGE}")

        url = f"{BASE_URL}/app/gallery?pageNum={page_num}"
        response = make_request(url)

        if not response:
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        # Ищем все ссылки на картины
        links = soup.find_all('a', href=re.compile(r'/masterpiece/\d+'))

        page_ids = []
        for link in links:
            href = link.get('href', '')
            match = re.search(r'/masterpiece/(\d+)', href)
            if match:
                artwork_id = match.group(1)
                page_ids.append(artwork_id)
                all_ids.add(artwork_id)

        print(f"  ✅ Найдено на странице: {len(page_ids)}")
        print(f"  📊 Всего собрано: {len(all_ids)}")

        # Сохраняем промежуточные результаты
        with open(IDS_FILE, 'w', encoding='utf-8') as f:
            for id_num in sorted(all_ids, key=int):
                f.write(f"{id_num}\n")

        # Пауза между страницами
        if page_num < END_PAGE:
            pause = random.uniform(3, 7)
            time.sleep(pause)

    # Сохраняем финальный список
    all_ids_list = sorted(all_ids, key=int)
    with open(IDS_FILE, 'w', encoding='utf-8') as f:
        for id_num in all_ids_list:
            f.write(f"{id_num}\n")

    print(f"\n✅ Сбор завершен!")
    print(f"📊 Всего ID: {len(all_ids_list)}")
    print(f"💾 Сохранено в: {IDS_FILE}")

    return all_ids_list


def get_artwork_info(artwork_id):
    """Получает информацию о картине по ID"""
    try:
        url = f"{BASE_URL}/app/masterpiece/{artwork_id}"
        print(f"\n🖼️ ID: {artwork_id}")

        response = make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Извлекаем изображение (самое важное!)
        image_url = None

        # Ищем тег img с атрибутом data-v-4c7e51de (как в вашем примере)
        img_tags = soup.find_all('img', attrs={'data-v-4c7e51de': True})
        for img in img_tags:
            src = img.get('src')
            if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                image_url = src
                break

        # Если не нашли, ищем любой тег img
        if not image_url:
            all_imgs = soup.find_all('img')
            for img in all_imgs:
                src = img.get('src')
                if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    # Пропускаем логотипы и иконки
                    if 'logo' not in src.lower() and 'icon' not in src.lower():
                        image_url = src
                        break

        if not image_url:
            print(f"  ❌ Изображение не найдено")
            return None

        # Делаем URL абсолютным
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        elif image_url.startswith('/'):
            image_url = urljoin(BASE_URL, image_url)
        elif not image_url.startswith('http'):
            image_url = urljoin(url, image_url)

        # 2. Извлекаем название из alt или других мест
        title = "Без названия"

        # Из alt тега img
        for img in soup.find_all('img'):
            alt = img.get('alt', '')
            if alt and alt != "Без названия" and len(alt) > 2:
                title = alt
                break

        # Ищем в заголовках
        if title == "Без названия":
            h1 = soup.find('h1')
            if h1:
                title = h1.text.strip()

        # 3. Извлекаем автора
        author = "Неизвестный автор"

        # Ищем по структуре (ваш пример с data-v-bb59db8a)
        author_spans = soup.find_all('span', attrs={'data-v-bb59db8a': True})
        if len(author_spans) >= 1:
            # Часто первый span - автор
            author = author_spans[0].text.strip()

        # Ищем текст "Автор:"
        if author == "Неизвестный автор":
            for elem in soup.find_all(text=re.compile(r'Автор:', re.I)):
                if elem.parent and elem.parent.find_next('span'):
                    author = elem.parent.find_next('span').text.strip()
                    break

        # Очищаем текст
        title = re.sub(r'\s+', ' ', title).strip()
        author = re.sub(r'\s+', ' ', author).strip()

        # Формируем имя файла
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        safe_author = re.sub(r'[<>:"/\\|?*]', '_', author)
        filename = f"{safe_author} - {safe_title}"

        print(f"  🖋️ Название: {title}")
        print(f"  👤 Автор: {author}")
        print(f"  🖼️ Изображение: {image_url.split('/')[-1][:30]}...")

        return {
            'id': artwork_id,
            'url': url,
            'image_url': image_url,
            'filename': filename,
            'title': title,
            'author': author
        }

    except Exception as e:
        print(f"  ❌ Ошибка: {str(e)[:100]}")
        return None


def download_artwork(artwork_info):
    """Скачивает картину по информации"""
    try:
        image_url = artwork_info['image_url']
        filename = artwork_info['filename']
        artwork_id = artwork_info['id']

        print(f"  📥 Скачиваю...")

        # Создаем папку для картины
        artwork_dir = os.path.join(SAVE_DIR, f"ID_{artwork_id}")
        os.makedirs(artwork_dir, exist_ok=True)

        # Загружаем изображение
        response = session.get(image_url, stream=True, timeout=30)
        response.raise_for_status()

        # Определяем расширение
        content_type = response.headers.get('content-type', '').lower()
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        elif 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            # По URL
            if '.png' in image_url.lower():
                ext = '.png'
            elif '.webp' in image_url.lower():
                ext = '.webp'
            else:
                ext = '.jpg'

        # Сохраняем изображение
        image_path = os.path.join(artwork_dir, f"{filename}{ext}")

        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Сохраняем метаданные
        meta_path = os.path.join(artwork_dir, 'info.txt')
        with open(meta_path, 'w', encoding='utf-8') as f:
            f.write(f"ID: {artwork_info['id']}\n")
            f.write(f"Название: {artwork_info['title']}\n")
            f.write(f"Автор: {artwork_info['author']}\n")
            f.write(f"URL страницы: {artwork_info['url']}\n")
            f.write(f"URL изображения: {artwork_info['image_url']}\n")
            f.write(f"Дата скачивания: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        file_size = os.path.getsize(image_path) / 1024
        print(f"  ✅ Скачано: {filename[:40]}... ({file_size:.1f} KB)")

        return True

    except Exception as e:
        print(f"  ❌ Ошибка скачивания: {str(e)[:100]}")
        return False


def load_progress():
    """Загружает прогресс скачивания"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'downloaded': [],
        'failed': [],
        'current_index': 0,
        'start_time': time.time()
    }


def save_progress(progress):
    """Сохраняет прогресс скачивания"""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def download_all_artworks(all_ids):
    """Скачивает все картины по списку ID"""
    print("\n" + "=" * 70)
    print("🚀 НАЧИНАЮ СКАЧИВАНИЕ КАРТИН")
    print("=" * 70)

    # Загружаем прогресс
    progress = load_progress()
    downloaded_ids = set(progress['downloaded'])
    failed_ids = set(progress['failed'])
    start_index = progress['current_index']

    print(f"📊 Всего ID для обработки: {len(all_ids)}")
    print(f"✅ Уже скачано: {len(downloaded_ids)}")
    print(f"❌ Не удалось ранее: {len(failed_ids)}")
    print(f"➡️ Начинаю с индекса: {start_index}")

    total_to_download = len(all_ids)
    success_count = len(downloaded_ids)
    fail_count = len(failed_ids)

    for i, artwork_id in enumerate(all_ids[start_index:], start=start_index):
        print(f"\n[{i + 1}/{total_to_download}] ", end="")

        # Пропускаем уже обработанные
        if artwork_id in downloaded_ids:
            print(f"⏭️ Уже скачано (ID: {artwork_id})")
            continue

        if artwork_id in failed_ids:
            print(f"🔄 Повторная попытка (ID: {artwork_id})")

        # Получаем информацию о картине
        artwork_info = get_artwork_info(artwork_id)

        if artwork_info:
            # Скачиваем картину
            if download_artwork(artwork_info):
                success_count += 1
                downloaded_ids.add(artwork_id)
                progress['downloaded'] = list(downloaded_ids)
                if artwork_id in failed_ids:
                    failed_ids.remove(artwork_id)
            else:
                fail_count += 1
                failed_ids.add(artwork_id)
                progress['failed'] = list(failed_ids)
        else:
            fail_count += 1
            failed_ids.add(artwork_id)
            progress['failed'] = list(failed_ids)

        # Обновляем прогресс
        progress['current_index'] = i + 1
        save_progress(progress)

        # Выводим статистику
        print(f"📊 Прогресс: ✅{success_count} ❌{fail_count}")

        # Пауза между картинами
        if i < total_to_download - 1:
            pause = random.uniform(2, 5)
            time.sleep(pause)

    print("\n" + "=" * 70)
    print("🎉 СКАЧИВАНИЕ ЗАВЕРШЕНО!")
    print("=" * 70)
    print(f"✅ Успешно скачано: {success_count}")
    print(f"❌ Не удалось: {fail_count}")
    print(f"📁 Папка с картинами: {SAVE_DIR}")

    # Сохраняем финальный отчет
    report_path = os.path.join(SAVE_DIR, 'final_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"Отчет о скачивании картин\n")
        f.write(f"Дата: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Всего ID: {total_to_download}\n")
        f.write(f"Успешно скачано: {success_count}\n")
        f.write(f"Не удалось: {fail_count}\n\n")

        if failed_ids:
            f.write("Не скачанные ID:\n")
            for id_num in sorted(failed_ids, key=int):
                f.write(f"{id_num}\n")


def main():
    """Основная функция"""
    print("=" * 70)
    print("🎨 СКАЧИВАТЕЛЬ КАРТИН - ТРЕТЬЯКОВСКАЯ ГАЛЕРЕЯ")
    print("=" * 70)
    print(f"📁 Папка для сохранения: {SAVE_DIR}")
    print(f"📄 Страницы для парсинга: {START_PAGE}-{END_PAGE}")
    print("=" * 70)

    # 1. Собираем все ID
    print("\n1️⃣ Этап 1: Сбор всех ID картин")
    all_ids = collect_all_ids()

    if not all_ids:
        print("❌ Не удалось собрать ID картин")
        return

    # 2. Скачиваем картины
    print("\n2️⃣ Этап 2: Скачивание картин")
    choice = input("🚀 Начать скачивание сейчас? (y/n): ").lower()

    if choice == 'y':
        download_all_artworks(all_ids)
    else:
        print(f"\n📋 ID сохранены в файл: {IDS_FILE}")
        print(f"📋 Всего ID: {len(all_ids)}")
        print(f"\nЧтобы начать скачивание позже, запустите:")
        print(f"python download_tretyakov_final.py --download")

    print("\n" + "=" * 70)
    print("🏁 ПРОГРАММА ЗАВЕРШЕНА")
    print("=" * 70)


if __name__ == "__main__":
    main()
